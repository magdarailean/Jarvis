"""Own exactly one frame and one cancellable activation timer on the GUI thread."""

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from .qt_capture import capture_screen


class CaptureSession(QObject):
    frame_changed = Signal(object)  # ScreenFrame or None; consumers must release old previews.
    finished = Signal()  # Restore hidden UI on success, cancellation or error.
    failed = Signal(str)  # Exception type only, never pixels or provider exception text.

    def __init__(self, parent=None, *, capture=capture_screen) -> None:
        super().__init__(parent)
        self._capture = capture
        self.frame = None
        self._screen = None
        self._signature = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._acquire)
        QApplication.instance().screenRemoved.connect(self._screen_removed)

    @property
    def pending(self) -> bool:
        return self._timer.isActive()

    def begin(self, screen, *, delay_ms: int = 3000) -> bool:
        if self.pending:
            return False
        if screen not in QApplication.instance().screens():
            raise ValueError("Capture target is unavailable")
        if delay_ms < 0:
            raise ValueError("Delay cannot be negative")
        self.clear()
        self._screen = screen
        self._signature = self._display_signature()
        screen.geometryChanged.connect(self._invalidate)
        screen.logicalDotsPerInchChanged.connect(self._invalidate)
        self._timer.start(delay_ms)
        return True

    def clear(self, *, notify_finished: bool = True) -> None:
        was_pending = self.pending
        self._timer.stop()
        if self._screen is not None:
            self._screen.geometryChanged.disconnect(self._invalidate)
            self._screen.logicalDotsPerInchChanged.disconnect(self._invalidate)
        self._screen = None
        self._signature = None
        self.frame = None
        self.frame_changed.emit(None)
        if was_pending and notify_finished:
            self.finished.emit()

    def _display_signature(self):
        return self._screen.geometry().getRect(), self._screen.devicePixelRatio()

    def _invalidate(self, *_args) -> None:
        self.clear()

    def _screen_removed(self, screen) -> None:
        if screen is self._screen:
            self.clear()

    def _acquire(self) -> None:
        if self._screen is None:
            return
        try:
            if self._display_signature() != self._signature:
                raise RuntimeError("Display changed before capture")
            frame = self._capture(self._screen)
            if self._display_signature() != self._signature:
                raise RuntimeError("Display changed during capture")
            self.frame = frame
            self.frame_changed.emit(frame)
        except Exception as error:
            # Capture is an external adapter: any failure must restore the desktop UI.
            self.clear(notify_finished=False)
            self.finished.emit()
            self.failed.emit(type(error).__name__)
            return
        self.finished.emit()
