"""Non-blocking Qt process adapter, with bounded startup/transcription lifetimes."""

import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class IonAdapter(QObject):
    ready = Signal()
    listening = Signal(int)
    stopped = Signal(int)
    transcribed = Signal(int, str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.available = False
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.errorOccurred.connect(lambda _: self._fail("Procesul vocal nu este disponibil."))
        self.process.finished.connect(self._finished)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self._fail("Serviciul vocal a depășit timpul de așteptare."))
        self._closing = False
        self._buffer = b""

    def warmup(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self._closing = False
        self._buffer = b""
        root = Path(__file__).resolve().parents[4]
        source = Path(os.environ.get("JARVIS_ION_SOURCE", str(root / "CursorMain" / "workingVersion1.py")))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONDONTWRITEBYTECODE", "1")
        env.insert("PYTHONUTF8", "1")
        self.process.setProcessEnvironment(env)
        self.process.start(sys.executable, ["-u", "-m", "jarvis.features.voice_input.ion_worker", str(source)])
        self.timer.start(120_000)

    def _send(self, command, **fields):
        self.process.write((json.dumps({"command": command, **fields}) + "\n").encode())

    def start(self, token):
        if not self.available:
            raise RuntimeError("Voice service is not ready")
        self._send("start", token=token)
        self.timer.start(15_000)  # Ion records at most ten seconds; catch device/start hangs.

    def stop(self):
        if self.available:
            self._send("stop")
            self.timer.start(120_000)

    def _read(self):
        self._buffer += bytes(self.process.readAllStandardOutput())
        if len(self._buffer) > 64_000:
            self._fail("Răspuns vocal invalid.")
            return
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                message = json.loads(line)
                event = message["event"]
                if event == "ready":
                    self.available = True
                    self.timer.stop()
                    self.ready.emit()
                elif event == "listening":
                    self.listening.emit(int(message["token"]))
                elif event == "stopped":
                    self.timer.start(120_000)
                    self.stopped.emit(int(message["token"]))
                elif event == "text":
                    self.timer.stop()
                    self.transcribed.emit(int(message["token"]), str(message["text"]))
                elif event == "error":
                    self._fail("Vocea nu este disponibilă. Verifică microfonul, dependențele Ion și modelul local.")
                    return
            except (ValueError, KeyError, TypeError):
                self._fail("Răspuns vocal invalid.")
                return

    def _finished(self, *_):
        if not self._closing:
            self._fail("Serviciul vocal s-a oprit. Verifică instalarea Ion.")

    def _fail(self, message):
        if self._closing:
            return
        self.close()
        self.failed.emit(message)

    def close(self):
        self._closing = True
        self.available = False
        self.timer.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1500)
        self._buffer = b""
