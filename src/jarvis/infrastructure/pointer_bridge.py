"""Process boundary calling the owner's existing GuidePointer API unchanged."""
import json
import sys
from PySide6.QtCore import QObject, QProcess, Signal


class PointerBridge(QObject):
    failed = Signal(str)
    shown = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.pending = None
        self.closing = False
        self._buffer = b""
        self.process.started.connect(self._flush)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.errorOccurred.connect(lambda _: self._error())
        self.process.finished.connect(lambda code, _: self._error() if code and not self.closing else None)

    def _error(self):
        if not self.closing:
            self.failed.emit("Indicatorul nu este disponibil. Instalează dependențele .[openrouter]. Răspunsul textual este păstrat.")

    def _read(self):
        self._buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            try:
                event = json.loads(line).get('event')
            except (ValueError, AttributeError):
                continue
            if event == 'pointed':
                self.shown.emit()
            elif event == 'target_unavailable':
                self.failed.emit("Indicatorul nu poate găsi monitorul țintei. Repetă comanda pe ecranul curent.")

    def show(self, action, screen):
        self.closing = False
        self.pending = dict(command="point", monitor=screen.name(), target=action.target)
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self._buffer = b""
            self.process.start(sys.executable, ['-B', '-m', 'jarvis.infrastructure.pointer_worker'])
        else:
            self._flush()

    def _flush(self):
        if self.pending is not None and self.process.state() == QProcess.ProcessState.Running:
            self.process.write((json.dumps(self.pending)+'\n').encode())
            self.pending = None

    def hide(self):
        self.pending = dict(command="hide")
        self._flush()

    def close(self):
        self.closing = True
        self.pending = None
        self._buffer = b""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1500)
