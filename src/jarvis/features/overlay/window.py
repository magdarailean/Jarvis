"""Qt overlay adapter. Call its public methods on the GUI thread only."""

import math
from dataclasses import replace
from shiboken6 import isValid

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QScreen
from PySide6.QtWidgets import QApplication, QWidget

from .model import Annotation, AnnotationScene, Shape
from jarvis.features.callouts.model import CalloutScene, VisualKind
from jarvis.features.callouts.layout import arrange
from jarvis.features.callouts.window import paint_callout
from jarvis.features.callouts.timing import CalloutTiming


class OverlayWindow(QWidget):
    """One transparent, input-transparent surface bound to one Qt screen.

    Qt paints in device-independent pixels and handles per-monitor scaling.
    A display geometry/DPI change or removal clears stale annotations. This
    does not track underlying application content or scrolling yet.
    """

    pointer_requested = Signal(object)  # Validated VisualAction; no cursor implementation here.
    pointer_cleared = Signal()

    def __init__(self, screen: QScreen) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self._scene = AnnotationScene()
        self._callouts = CalloutScene()
        self.callout_timing = CalloutTiming(self)
        self.callout_timing.changed.connect(self.update)
        self.callout_timing.expired.connect(self._remove_callout)
        self._target_screen = screen
        self.setObjectName("JarvisOverlay")
        self.setWindowTitle("Jarvis — Adnotări")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        screen.geometryChanged.connect(self._display_changed)
        screen.logicalDotsPerInchChanged.connect(self._display_changed)
        QApplication.instance().screenRemoved.connect(self._screen_removed)

    @property
    def annotations(self) -> tuple[Annotation, ...]:
        return self._scene.annotations

    @property
    def callouts(self):
        return self._callouts.items

    @property
    def has_visuals(self):
        return any(item.visible for item in (*self.annotations, *self.callouts))

    def apply_visual_plan(self, plan):
        if any(action.kind == VisualKind.CALLOUT for action in plan.actions):
            self.clear_temporary_callouts()
        for action in plan.actions:
            try:
                if action.kind == VisualKind.CALLOUT:
                    if self._target_screen is None:
                        continue
                    if (action.id not in {item.id for item in self.callouts}
                            and sum(item.visible for item in self.callouts) >= 2):
                        continue
                    self._callouts.upsert(action.callout)
                    self.callout_timing.start(action.callout)
                    self._scene.remove(action.id)
                elif action.kind == VisualKind.POINTER:
                    self.pointer_requested.emit(action)
                elif action.kind != VisualKind.NONE:
                    self.upsert(action.annotation)
            except (ValueError, TypeError, RuntimeError):
                continue  # One invalid/unrenderable action never discards siblings or answer.
        self._refresh()
        return plan.text

    def upsert(self, annotation: Annotation) -> None:
        if self._target_screen is None:
            raise RuntimeError("Overlay target screen was removed; create a new overlay")
        self._scene.upsert(annotation)
        self._callouts.remove(annotation.id)
        self.callout_timing.remove(annotation.id)
        self._refresh()

    def set_visible(self, annotation_id: str, visible: bool) -> None:
        item = next((item for item in self.callouts if item.id == annotation_id), None)
        if item is not None:
            self._callouts.upsert(replace(item, visible=visible))
        else:
            self._scene.set_visible(annotation_id, visible)
        self._refresh()

    def highlight(self, annotation_id: str, enabled: bool = True) -> None:
        if any(item.id == annotation_id for item in self.callouts):
            self._callouts.highlight(annotation_id, enabled)
        else:
            self._scene.highlight(annotation_id, enabled)
        self._refresh()

    def remove(self, annotation_id: str) -> None:
        self._scene.remove(annotation_id)
        self._callouts.remove(annotation_id)
        self.callout_timing.remove(annotation_id)
        self._refresh()

    def _remove_callout(self, identifier):
        self._callouts.remove(identifier)
        self.callout_timing.remove(identifier)
        if not self.has_visuals:
            self.hide()
        self.update()  # Expiry must not re-show an overlay hidden for capture.

    def clear_temporary_callouts(self):
        for item in self.callouts:
            if item.temporary:
                self._remove_callout(item.id)

    def clear(self) -> None:
        self.pointer_cleared.emit()
        self._scene.clear()
        self._callouts.clear()
        self.callout_timing.clear()
        self.hide()
        self.update()

    def _refresh(self) -> None:
        self.setVisible(self.has_visuals)
        self.update()

    def _display_changed(self, *_args) -> None:
        self.clear()
        if self._target_screen is not None and isValid(self._target_screen):
            self.setGeometry(self._target_screen.geometry())
        else:
            self._target_screen = None

    def _screen_removed(self, screen: QScreen) -> None:
        if screen is self._target_screen:
            self.clear()
            self._target_screen = None

    def closeEvent(self, event) -> None:
        self.clear()
        super().closeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for item in self.annotations:
            if item.visible:
                self._paint_annotation(painter, item)
        occupied = []
        protected = [QRectF(t[0]*self.width(), t[1]*self.height(),
                            (t[2]-t[0])*self.width(), (t[3]-t[1])*self.height())
                     for item in self.callouts if item.visible and (t := item.target) is not None]
        for item in sorted(self.callouts, key=lambda item: item.target is None):
            if item.visible:
                layout = arrange(item, self.width(), self.height(), occupied, protected)
                if layout is not None:
                    paint_callout(painter, item, layout, self.callout_timing.count(item.id))
                    occupied.append(layout.bubble)
        painter.end()

    def _paint_annotation(self, painter: QPainter, item: Annotation) -> None:
        x1, y1, x2, y2 = item.bounds
        start = QPointF(x1 * self.width(), y1 * self.height())
        end = QPointF(x2 * self.width(), y2 * self.height())
        bounds = QRectF(start, end)
        color = QColor("#f59e0b" if item.highlighted else "#1685e6")
        painter.setPen(QPen(color, 5 if item.highlighted else 3))
        fill = QColor(color)
        fill.setAlpha(45)
        painter.setBrush(fill)
        if item.shape == Shape.RECTANGLE:
            painter.drawRoundedRect(bounds, 6, 6)
        elif item.shape == Shape.ELLIPSE:
            painter.drawEllipse(bounds)
        elif item.shape in (Shape.LINE, Shape.ARROW):
            painter.drawLine(start, end)
            if item.shape == Shape.ARROW:
                angle = math.atan2(end.y() - start.y(), end.x() - start.x())
                length = min(18, math.hypot(end.x() - start.x(), end.y() - start.y()) * 0.4)
                points = [end] + [QPointF(end.x() - length * math.cos(angle + delta),
                                        end.y() - length * math.sin(angle + delta))
                                  for delta in (-0.5, 0.5)]
                painter.setBrush(color)
                painter.drawPolygon(QPolygonF(points))
        elif item.shape == Shape.LABEL:
            painter.setBrush(QColor(15, 35, 58, 235))
            painter.drawRoundedRect(bounds, 8, 8)
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Segoe UI")
            font.setPixelSize(18)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(bounds.adjusted(10, 6, -10, -6),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                             | Qt.TextFlag.TextWordWrap, item.text)
