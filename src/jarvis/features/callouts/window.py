"""Isolated, click-through callout layer. No cursor imports or hooks."""
import math
from shiboken6 import isValid

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QPalette, QAbstractTextDocumentLayout, QTextCursor
from PySide6.QtWidgets import QApplication, QWidget

from .layout import arrange, PAD
from .model import CalloutScene, VisualKind
from .timing import CalloutTiming


class CalloutOverlay(QWidget):
    def __init__(self, screen):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.scene = CalloutScene()
        self.timing = CalloutTiming(self)
        self.timing.changed.connect(self.update)
        self.timing.expired.connect(self.remove)
        self.target_screen = screen
        self.setWindowTitle("Jarvis — Explicații")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        screen.geometryChanged.connect(self.invalidate)
        screen.logicalDotsPerInchChanged.connect(self.invalidate)
        QApplication.instance().screenRemoved.connect(self.screen_removed)

    def upsert(self, item):
        if self.target_screen is None:
            return
        self.scene.upsert(item)
        self.timing.start(item)
        self.refresh()

    def apply_plan(self, plan):
        for action in plan.actions:
            if action.kind == VisualKind.CALLOUT:
                try:
                    self.upsert(action.callout)
                except (ValueError, TypeError):
                    pass
        return plan.text

    def remove(self, identifier):
        self.timing.remove(identifier)
        self.scene.remove(identifier)
        self.refresh()

    def highlight(self, identifier, enabled=True):
        self.scene.highlight(identifier, enabled)
        self.refresh()

    def refresh(self):
        self.setVisible(any(item.visible for item in self.scene.items))
        self.update()

    def clear(self):
        self.timing.clear()
        self.scene.clear()
        self.hide()
        self.update()

    def invalidate(self, *_):
        self.clear()
        if self.target_screen is not None and isValid(self.target_screen):
            self.setGeometry(self.target_screen.geometry())
        else:
            self.target_screen = None

    def screen_removed(self, screen):
        if screen is self.target_screen:
            self.clear()
            self.target_screen = None

    def closeEvent(self, event):
        self.clear()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        occupied = []
        for item in self.scene.items:
            if item.visible:
                layout = arrange(item, self.width(), self.height(), occupied)
                if layout is not None:
                    paint_callout(painter, item, layout, self.timing.count(item.id))
                    occupied.append(layout.bubble)
        painter.end()


def paint_callout(painter, item, layout, visible_chars=None):
    painter.save()
    accent = QColor("#fbbf24" if item.highlighted else "#d1d5db")
    if layout.start is not None:
        painter.setPen(QPen(QColor("#171717"), 5))
        painter.drawLine(layout.start, layout.end)
        painter.setPen(QPen(accent, 2))
        painter.drawLine(layout.start, layout.end)
        delta = layout.end - layout.start
        angle = math.atan2(delta.y(), delta.x())
        points = [layout.end] + [QPointF(layout.end.x()-10*math.cos(angle+d),
                                        layout.end.y()-10*math.sin(angle+d)) for d in (-0.45, 0.45)]
        painter.setBrush(accent)
        painter.drawPolygon(QPolygonF(points))
    painter.setBrush(QColor(18, 20, 24, 248))
    painter.setPen(QPen(accent if item.highlighted else QColor("#59616d"), 2 if item.highlighted else 1))
    painter.drawRoundedRect(layout.bubble, 12, 12)
    painter.translate(layout.bubble.left()+PAD, layout.bubble.top()+PAD)
    context = QAbstractTextDocumentLayout.PaintContext()
    context.palette.setColor(QPalette.ColorRole.Text, QColor("white"))
    if visible_chars is not None and visible_chars < len(item.text):
        # Keep the complete document layout stable; only hide unrevealed glyphs.
        selection = QAbstractTextDocumentLayout.Selection()
        selection.cursor = QTextCursor(layout.text)
        position = len(item.text[:visible_chars].encode('utf-16-le')) // 2
        selection.cursor.setPosition(position)
        selection.cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        selection.format.setForeground(QColor(0, 0, 0, 0))
        context.selections = [selection]
    layout.text.documentLayout().draw(painter, context)
    painter.restore()
