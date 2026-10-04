"""Click-through captions and cancellable Romanian speech for version 4."""
import asyncio
import threading

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QPoint, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtGui import QColor, QPainter, QPen

import diagnostics_v2 as diagnostics


class TargetCaption(QLabel):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.WindowTransparentForInput
                            | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setStyleSheet("QLabel { color: white; padding: 8px 12px; font-size: 13px; }")

    def paintEvent(self, event):
        # Native translucent windows do not always paint a QLabel CSS background.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#172033"))
        painter.setPen(QPen(QColor("#3380ff"), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        painter.end()
        super().paintEvent(event)

    def show_at(self, text, x, y):
        bounds = (QApplication.screenAt(QPoint(round(x), round(y)))
                  or QApplication.primaryScreen()).availableGeometry()
        self.setFixedWidth(min(260, bounds.width()))
        caption = " ".join(text.split())
        if len(caption) > 120:
            caption = caption[:117].rsplit(" ", 1)[0] + "…"
        self.setText(caption)
        self.adjustSize()
        # Prefer the lower right; flip to the opposite side at screen edges.
        left = x + 24 if x + 24 + self.width() <= bounds.right() + 1 else x - self.width() - 24
        top = y + 28 if y + 28 + self.height() <= bounds.bottom() + 1 else y - self.height() - 20
        self.move(round(max(bounds.left(), min(left, bounds.right() - self.width() + 1))),
                  round(max(bounds.top(), min(top, bounds.bottom() - self.height() + 1))))
        self.show()


class SpeechOutputRequest(QThread):
    ready = pyqtSignal(int, bytes)
    failed = pyqtSignal(int)

    def __init__(self, token, text, voice, parent=None):
        super().__init__(parent)
        self.token, self.text, self.voice = token, text, voice
        self.cancelled = threading.Event()
        self.loop = self.task = None

    def cancel(self):
        self.cancelled.set()
        loop, task = self.loop, self.task
        if loop and task:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # Event loop already finished.

    async def generate(self):
        import edge_tts
        self.loop = asyncio.get_running_loop()
        self.task = asyncio.current_task()
        if self.cancelled.is_set():
            return b""
        audio = bytearray()
        speech = edge_tts.Communicate(self.text, self.voice, connect_timeout=10, receive_timeout=15)
        async for chunk in speech.stream():
            if self.cancelled.is_set():
                return b""
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        if not audio:
            raise ValueError("No speech audio returned.")
        return bytes(audio)

    def run(self):
        try:
            async def bounded():
                return await asyncio.wait_for(self.generate(), timeout=25)
            audio = asyncio.run(bounded())
            if audio and not self.cancelled.is_set():
                self.ready.emit(self.token, audio)
        except asyncio.CancelledError:
            pass
        except Exception as error:
            if not self.cancelled.is_set():
                # Do not log remote messages that might contain spoken text.
                diagnostics.event("tts.error", error_type=type(error).__name__)
                self.failed.emit(self.token)
        finally:
            self.loop = self.task = None
            self.text = ""


class SpeechOutput(QObject):
    drained = pyqtSignal()

    def __init__(self, enabled=True, voice="ro-RO-AlinaNeural", parent=None):
        super().__init__(parent)
        self.enabled, self.voice = enabled, voice
        self.token = 0
        self.requests = set()
        self.player = self.output = self.buffer = None

    def stop(self):
        self.token += 1
        for request in self.requests:
            request.cancel()
        if self.player:
            self.player.stop()
            self.player.setSource(QUrl())
        if self.buffer:
            self.buffer.close()
            self.buffer.deleteLater()
            self.buffer = None

    def say(self, text):
        self.stop()
        if not self.enabled or not text.strip():
            return
        request = SpeechOutputRequest(self.token, text.strip()[:500], self.voice, self)
        self.requests.add(request)
        request.ready.connect(self.play)
        request.finished.connect(self.finished)
        request.start()

    def play(self, token, audio):
        if token != self.token:
            return
        try:
            if self.player is None:
                from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
                self.output = QAudioOutput(self)
                self.player = QMediaPlayer(self)
                self.player.setAudioOutput(self.output)
                self.player.errorOccurred.connect(
                    lambda *_: diagnostics.event("tts.playback.error"))
            self.buffer = QBuffer(self)
            self.buffer.setData(QByteArray(audio))
            self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.player.setSourceDevice(self.buffer, QUrl("speech.mp3"))
            self.player.play()
        except Exception as error:
            diagnostics.event("tts.playback.error", error_type=type(error).__name__)

    def finished(self):
        request = self.sender()
        self.requests.discard(request)
        request.deleteLater()
        if not self.requests:
            self.drained.emit()
