"""Qt one-shot capture adapter. GUI-thread use only; no files or network."""

from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QScreen

from .model import ScreenFrame, ScreenGeometry


MAX_PIXELS = 40_000_000


def capture_screen(screen: QScreen) -> ScreenFrame:
    rect = screen.geometry()
    dpr = screen.devicePixelRatio()
    if rect.width() * rect.height() * dpr * dpr > MAX_PIXELS:
        raise ValueError("Screen exceeds capture size limit")
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise RuntimeError("Screen capture unavailable")
    if pixmap.width() * pixmap.height() > MAX_PIXELS:
        raise ValueError("Captured image exceeds size limit")
    geometry = ScreenGeometry(screen.name(), rect.x(), rect.y(), rect.width(), rect.height(),
                              pixmap.width(), pixmap.height(), pixmap.devicePixelRatio())
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Image buffer unavailable")
    try:
        if not pixmap.save(buffer, "PNG"):
            raise RuntimeError("Image encoding failed")
        png = bytes(buffer.data())
    finally:
        buffer.close()
    return ScreenFrame(uuid4().hex, datetime.now(timezone.utc).isoformat(), geometry, png)
