"""Qt process boundary for cancellable synthesis/playback. No visual lifecycle."""
import json
import sys
from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class SpeechService(QObject):
    preparing = Signal()
    started = Signal()
    finished = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.jobs = set()
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self._fail)

    @property
    def busy(self):
        return self.process is not None

    def say(self, text):
        self.stop()
        if not isinstance(text, str) or not text.strip():
            return
        process = QProcess(self)
        process.buffer = b''
        process.played = False
        self.process = process
        self.jobs.add(process)
        process.started.connect(lambda: self._write(process, text))
        process.readyReadStandardOutput.connect(lambda: self._read(process))
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.errorOccurred.connect(lambda _: self._fail() if self.process is process else None)
        process.finished.connect(lambda code, _: self._finished(process, code))
        self.timeout.start(45000)
        self.preparing.emit()
        process.start(sys.executable, ['-B', '-m', 'jarvis.features.speech.worker'])

    def _write(self, process, text):
        if process is self.process:
            process.write((json.dumps({'text': text}, ensure_ascii=True)+'\n').encode())
            process.closeWriteChannel()

    def _read(self, process):
        data = bytes(process.readAllStandardOutput())
        if process is not self.process:
            return
        process.buffer += data
        if len(process.buffer) > 4096:
            self._fail()
            return
        while b'\n' in process.buffer:
            line, process.buffer = process.buffer.split(b'\n', 1)
            if process is not self.process:
                return
            try:
                event = json.loads(line)['event']
            except (ValueError, KeyError, TypeError):
                self._fail()
                return
            if event == 'started':
                process.played = True
                self.timeout.start(600000)
                self.started.emit()
            elif event == 'error':
                self._fail()

    def _finished(self, process, code):
        self._read(process)
        if process is self.process:
            self.process = None
            self.timeout.stop()
            if code == 0 and process.played:
                self.finished.emit()
            else:
                self.failed.emit(self.failure_message())
        self.jobs.discard(process)
        process.deleteLater()

    @staticmethod
    def failure_message():
        return "Redarea vocală nu este disponibilă. Răspunsul și explicațiile vizuale rămân disponibile."

    def _fail(self):
        if not self.busy:
            return
        self.stop()
        self.failed.emit(self.failure_message())

    def stop(self):
        process, self.process = self.process, None
        self.timeout.stop()
        if process is not None:
            process.kill()  # No GUI-thread wait. Late events are rejected by identity.

    def close(self):
        self.stop()
        # Only application shutdown waits to reap workers, never PTT interruption.
        for process in tuple(self.jobs):
            process.kill()
            process.waitForFinished(1000)
