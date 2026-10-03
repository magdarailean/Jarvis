import math
import signal
import sys
import time

from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QApplication, QWidget


class Companion(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.cursor_scale = 0.5
        self.setFixedSize(math.ceil(70 * self.cursor_scale), 
                          math.ceil(70 * self.cursor_scale))

        # Local drawing coordinates: the arrow tip is the pointing anchor.
        self.pointer_tip = QPoint(10, 8)
        self.pointer_color = QColor("#3380FF")

        self.follow_cursor = True

        self.animation = QPropertyAnimation(self, b"pos", self)
        self.animation.setDuration(900)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.finished.connect(self.after_pointing)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)

        self.update_position()
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.cursor_scale, self.cursor_scale)

        # Change these vertices to customize the cursor's shape.
        pointer = QPolygonF([
            QPointF(self.pointer_tip),
            QPointF(13, 56),
            QPointF(25, 44),
            QPointF(37, 64),
            QPointF(47, 58),
            QPointF(35, 38),
            QPointF(53, 36),
        ])
        # painter.setPen(QPen(QColor("white"), 1.5))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.pointer_color)
        painter.drawPolygon(pointer)

        painter.end()

    def update_position(self):
        if self.follow_cursor:
            cursor = QCursor.pos()
            self.move(cursor.x() + 25, cursor.y() + 20)

    def point_at(self, x, y):
        self.follow_cursor = False
        self.animation.stop()
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(
            QPoint(round(x - self.pointer_tip.x() * self.cursor_scale), 
                   round(y - self.pointer_tip.y() * self.cursor_scale),
                   )
        )
        self.animation.start()

    def after_pointing(self):
        QTimer.singleShot(2000, self.resume_following)

    def resume_following(self):
        self.follow_cursor = True


def main():
    app = QApplication(sys.argv)
    companion = Companion()

    signal.signal(signal.SIGINT, lambda *_: app.quit())

    # Demo: after five seconds, move to the primary screen's centre.
    centre = app.primaryScreen().geometry().center()
    companion.point_at(centre.x(), centre.y()),

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
