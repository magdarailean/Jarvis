from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def create_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1d5590"))
        painter.drawEllipse(1, 1, size - 2, size - 2)
        font = QFont("Segoe UI")
        font.setPixelSize(round(size * 0.6))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "J")
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class TrayIcon:
    def __init__(self, reopen: Callable[[], None], exit_app: Callable[[], None]) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise RuntimeError("System tray unavailable.")
        self.menu = QMenu()
        self.status_action = self.menu.addAction("Gata · Microfon oprit")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        self.open_action = self.menu.addAction("Deschide Jarvis")
        self.exit_action = self.menu.addAction("Ieșire")
        self.open_action.triggered.connect(reopen)
        self.exit_action.triggered.connect(exit_app)
        self.icon = QSystemTrayIcon(create_icon())
        self.icon.setToolTip("Jarvis — Gata · Microfon oprit")
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(
            lambda reason: reopen() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self.icon.show()

    def close(self) -> None:
        self.icon.hide()
        self.icon.deleteLater()
        self.menu.close()
        self.menu.deleteLater()
