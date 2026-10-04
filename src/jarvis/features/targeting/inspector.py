"""Opt-in visual diagnosis of the exact encoded image sent to the provider."""
import json

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget


class TargetInspector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.WindowDoesNotAcceptFocus
                            | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Jarvis — Diagnostic țintă")
        self.resize(900, 600)
        self.image = QImage()
        self.planned = self.located = None
        self.instruction = ""

    def present(self, image, planned, located):
        self.image = QImage.fromData(image)
        if self.image.isNull():
            self.clear()
            return
        self.planned = json.loads(planned).get("target")
        result = json.loads(located)
        self.located = result.get("target")
        self.instruction = result["instruction"]
        self.show()
        self.update()

    def clear(self):
        self.hide()
        self.image = QImage()
        self.planned = self.located = None
        self.instruction = ""

    def image_rect(self):
        if self.image.isNull():
            return QRectF()
        scale = min(self.width() / self.image.width(), max(1, self.height()-100) / self.image.height())
        width, height = self.image.width()*scale, self.image.height()*scale
        return QRectF((self.width()-width)/2, 100, width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#18202b"))
        painter.setPen(QColor("white"))
        painter.drawText(12, 22, "ALBASTRU: plan inițial · ROȘU: ținta finală · Escape: închide sesiunea")
        painter.drawText(QRectF(12, 32, self.width()-24, 62), Qt.TextFlag.TextWordWrap, self.instruction)
        rect = self.image_rect()
        if rect.isEmpty():
            return
        painter.drawImage(rect, self.image)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for bounds, color in ((self.planned, "#38bdf8"), (self.located, "#ff4444")):
            if bounds:
                painter.setPen(QPen(QColor(color), 2))
                painter.drawRect(QRectF(rect.x()+bounds["left"]*rect.width(),
                                        rect.y()+bounds["top"]*rect.height(),
                                        (bounds["right"]-bounds["left"])*rect.width(),
                                        (bounds["bottom"]-bounds["top"])*rect.height()))


def install_inspector(owner):
    class InspectableController(owner.GuideController):
        def __init__(self, *args, **kwargs):
            self.target_inspector = TargetInspector()
            super().__init__(*args, **kwargs)

        def begin_capture(self, purpose):
            self.target_inspector.clear()  # Exclude inspector from the next capture.
            super().begin_capture(purpose)

        def accept_decision(self, token, decision):
            worker = self.sender()
            review = getattr(worker, "target_review", None)
            if worker is not None and hasattr(worker, "target_review"):
                del worker.target_review
            current = token == self.generation and not self.closing
            super().accept_decision(token, decision)
            if current and token == self.generation and not self.closing and review:
                self.target_inspector.present(*review)

        def cancel_session(self):
            self.target_inspector.clear()
            super().cancel_session()

        def shutdown(self):
            self.target_inspector.clear()
            super().shutdown()

    owner.GuideController = InspectableController
