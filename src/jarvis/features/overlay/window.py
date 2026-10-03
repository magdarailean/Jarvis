"""Qt overlay adapter. Call its public methods on the GUI thread only."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QScreen
from PySide6.QtWidgets import QApplication, QWidget

from .model import Annotation, AnnotationScene, Shape


class OverlayWindow(QWidget):
    """One transparent, input-transparent surface bound to one Qt screen.

    Qt paints in device-independent pixels and handles per-monitor scaling.
    A display geometry/DPI change or removal clears stale annotations. This
    does not track underlying application content or scrolling yet.
    """

    def __init__(self, screen: QScreen) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self._scene = AnnotationScene()
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

    def upsert(self, annotation: Annotation) -> None:
        if self._target_screen is None:
            raise RuntimeError("Overlay target screen was removed; create a new overlay")
        self._scene.upsert(annotation)
        self._refresh()

    def set_visible(self, annotation_id: str, visible: bool) -> None:
        self._scene.set_visible(annotation_id, visible)
        self._refresh()

    def highlight(self, annotation_id: str, enabled: bool = True) -> None:
        self._scene.highlight(annotation_id, enabled)
        self._refresh()

    def remove(self, annotation_id: str) -> None:
        self._scene.remove(annotation_id)
        self._refresh()

    def clear(self) -> None:
        self._scene.clear()
        self.hide()
        self.update()

    def _refresh(self) -> None:
        self.setVisible(any(item.visible for item in self.annotations))
        self.update()

    def _display_changed(self, *_args) -> None:
        self.clear()
        if self._target_screen is not None:
            self.setGeometry(self._target_screen.geometry())

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
