"""Process boundary calling the owner's existing GuidePointer API unchanged."""
import json
import sys
from PySide6.QtCore import QObject, QProcess, Signal


class PointerBridge(QObject):
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.pending = None
        self.closing = False
        self.process.started.connect(self._flush)
        self.process.readyReadStandardOutput.connect(lambda: self.process.readAllStandardOutput())
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.errorOccurred.connect(lambda _: self._error())
        self.process.finished.connect(lambda code, _: self._error() if code and not self.closing else None)

    def _error(self):
        if not self.closing:
            self.failed.emit("Indicatorul nu este disponibil. Instalează dependențele .[openrouter]. Răspunsul textual este păstrat.")

    def show(self, action, screen):
        self.closing = False
        self.pending = dict(command="point", monitor=screen.name(), target=action.target)
        if self.process.state() == QProcess.ProcessState.NotRunning:
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
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1500)
