import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel


def foreground_screen(app):
    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]
    native = ctypes.WinDLL("user32", use_last_error=True)
    native.GetForegroundWindow.restype = wintypes.HWND
    native.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    native.MonitorFromWindow.restype = wintypes.HANDLE
    native.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(info)
    monitor = native.MonitorFromWindow(native.GetForegroundWindow(), 2)
    if native.GetMonitorInfoW(monitor, ctypes.byref(info)):
        for screen in app.screens():
            if screen.name().casefold() == info.szDevice.casefold():
                return screen
    return app.screenAt(QCursor.pos()) or app.primaryScreen()


class StatusIndicator(QLabel):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setStyleSheet("background:#172b43; color:white; padding:12px; border-radius:8px; font-size:15px;")
        self.setMaximumWidth(460)
        self.setWordWrap(True)

    def display(self, text, screen):
        self.setText(text)
        self.adjustSize()
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 20, area.bottom() - self.height() - 20)
        self.show()
