"""Isolated Ion adapter. JSON pipes only; never execute Ion's AI/demo main()."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time


class RecordingControl:
    """Wrap Ion's sounddevice dependency to stop its fixed-length recording early.

    Ion still owns rec()/wait(), audio format and transcription. Only one recording
    exists in this process. The unused tail of sd.rec's allocated buffer is removed
    using elapsed recording time (an estimate, not a sample-accurate callback count).
    """

    def __init__(self, sounddevice, started):
        self.device = sounddevice
        self.started = started
        self.lock = threading.Lock()
        self.stopping = False
        self.active = False
        self.duration = 0.0
        self.began = 0.0

    def rec(self, **kwargs):
        with self.lock:
            if self.stopping:
                raise InterruptedError()
            self.began = time.monotonic()
            audio = self.device.rec(**kwargs)
            self.active = True
            self.started()
            return audio

    def wait(self):
        self.device.wait()
        with self.lock:
            if not self.stopping:
                self.duration = time.monotonic() - self.began
            self.active = False

    def stop(self):
        with self.lock:
            if not self.stopping:
                self.stopping = True
                self.duration = time.monotonic() - self.began if self.active else 0
                if self.active:
                    self.device.stop()


def load_ion(path):
    # Do not write __pycache__ into the owner's directory.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("jarvis_ion_readonly", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "record_voice", None)) or not callable(getattr(module, "transcribe_voice", None)):
        raise RuntimeError("Ion API unavailable")
    return module


def main():
    protocol = sys.stdout
    sys.stdout = sys.stderr  # Ion's print() is never protocol or application logging.
    output_lock = threading.Lock()

    def emit(event, **fields):
        with output_lock:
            protocol.write(json.dumps({"event": event, **fields}, ensure_ascii=True) + "\n")
            protocol.flush()

    try:
        ion = load_ion(Path(sys.argv[1]))
        model = ion.WhisperModel(os.environ.get("JARVIS_ION_MODEL", "large-v3"),
                                 device="cpu", compute_type="int8", local_files_only=True)
    except Exception as error:
        emit("error", code=type(error).__name__)
        return 1
    device = ion.sd
    emit("ready")
    job = None
    control = None

    def record_and_transcribe(token, adapter):
        try:
            ion.sd = adapter  # Instance-local dependency adaptation; source remains untouched.
            audio = ion.record_voice()
            emit("stopped", token=token)
            samples = min(len(audio), max(0, int(adapter.duration * ion.SAMPLE_RATE)))
            text = "" if samples < ion.SAMPLE_RATE * 0.15 else ion.transcribe_voice(model, audio[:samples])
            emit("text", token=token, text=text[:2001])
        except InterruptedError:
            emit("text", token=token, text="")
        except Exception as error:
            emit("error", token=token, code=type(error).__name__)
        finally:
            adapter.stop()

    try:
        for line in sys.stdin:
            command = json.loads(line)
            if command["command"] == "start":
                if job is not None:
                    job.join(0.1)  # Previous terminal message may precede thread teardown.
                if job is not None and job.is_alive():
                    emit("error", code="Busy")
                    continue
                token = command["token"]
                control = RecordingControl(device, lambda token=token: emit("listening", token=token))
                job = threading.Thread(target=record_and_transcribe, args=(token, control), daemon=True)
                job.start()
            elif command["command"] == "stop" and control is not None:
                control.stop()
            elif command["command"] == "quit":
                break
    finally:
        if control is not None:
            control.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
