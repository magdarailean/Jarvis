"""Synthetic nine-point check; no capture, microphone or network calls."""
import sys

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QCursor
from PyQt6.QtWidgets import QApplication, QWidget


def run(owner):
    app = QApplication(sys.argv[:1])
    screen = app.screenAt(QCursor.pos()) or app.primaryScreen()

    class Grid(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setGeometry(screen.geometry())
            self.index = -1
            self.points = [(x, y) for y in (.2, .5, .8) for x in (.2, .5, .8)]
            self.pointer = owner.GuidePointer()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.advance)
            self.timer.start(2200)
            self.show()
            self.pointer.show()
            self.pointer.raise_()
            self.advance()

        def advance(self):
            self.index = (self.index + 1) % len(self.points)
            x, y = self.points[self.index]
            bounds = screen.geometry()
            self.pointer.point_at(bounds.x() + x * bounds.width(), bounds.y() + y * bounds.height())
            self.update()

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#18202b"))
            painter.setPen(QColor("white"))
            painter.drawText(30, 40, "Vârful săgeții trebuie să atingă centrul cercului verde. Escape: închide.")
            painter.drawText(30, 65, f"Monitor: {screen.name()} · Scalare: {screen.devicePixelRatio():g}")
            for index, (x, y) in enumerate(self.points):
                painter.setPen(QPen(QColor("#30e890" if index == self.index else "#64748b"), 2))
                point = QPointF(x * self.width(), y * self.height())
                painter.drawEllipse(point, 12, 12)
                painter.drawLine(QPointF(point.x() - 18, point.y()), QPointF(point.x() + 18, point.y()))
                painter.drawLine(QPointF(point.x(), point.y() - 18), QPointF(point.x(), point.y() + 18))

        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Escape:
                self.close()

        def closeEvent(self, event):
            self.timer.stop()
            self.pointer.close()
            app.quit()

    grid = Grid()
    app.exec()
