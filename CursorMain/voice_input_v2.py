"""Cancellable voice input; recordings and transcripts stay in memory."""
from __future__ import annotations

import os
from pathlib import Path
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal
import diagnostics_v2 as diagnostics


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.05


class SpeechGate:
    """RMS-based endpoint detector, with a minimum amount of voiced audio."""
    def __init__(self, threshold=0.01, silence_seconds=1.2,
                 start_timeout=8.0, max_seconds=30.0):
        self.threshold = threshold
        self.silence_seconds = silence_seconds
        self.start_timeout = start_timeout
        self.max_seconds = max_seconds
        self.elapsed = self.voiced = self.quiet = 0.0

    @property
    def has_speech(self):
        return self.voiced >= 0.2

    def observe(self, rms, duration=BLOCK_SECONDS):
        self.elapsed += duration
        if rms >= self.threshold:
            self.voiced += duration
            self.quiet = 0.0
        else:
            self.quiet += duration
        return (self.elapsed >= self.max_seconds
                or (not self.has_speech and self.elapsed >= self.start_timeout)
                or (self.has_speech and self.quiet >= self.silence_seconds))


class SpeechEngine:
    """Reuse one local Whisper model; serialize access across cancelled sessions."""
    def __init__(self, model="small"):
        self.model_name = model
        self.model = None
        self.lock = threading.Lock()

    def transcribe(self, audio, cancelled):
        with self.lock:
            if cancelled.is_set():
                return ""
            if self.model is None:
                started = time.monotonic()
                diagnostics.event("voice.model.load.start", model=self.model_name)
                # Download/cache only inside CursorMain; no recording is written.
                os.environ.setdefault("HF_HOME", str(BASE_DIR / "models" / "hf"))
                os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
                from faster_whisper import WhisperModel
                try:
                    self.model = WhisperModel(
                        self.model_name, device="cpu", compute_type="int8",
                        cpu_threads=max(1, min(4, (os.cpu_count() or 2) // 2)),
                        download_root=str(BASE_DIR / "models"),
                    )
                except Exception as error:
                    diagnostics.exception("voice.model.load.error", error, model=self.model_name)
                    raise
                diagnostics.event("voice.model.load.ready", model=self.model_name,
                                  elapsed_seconds=round(time.monotonic() - started, 2))
            if cancelled.is_set():
                return ""
            segments, _ = self.model.transcribe(
                audio, language="ro", beam_size=3, temperature=0.0,
                vad_filter=True, condition_on_previous_text=False,
            )
            parts = []
            for segment in segments:
                if cancelled.is_set():
                    return ""
                parts.append(segment.text.strip())
            return " ".join(parts).strip()


class VoiceRequest(QThread):
    listening = pyqtSignal(int)
    processing = pyqtSignal(int)
    recognized = pyqtSignal(int, str)
    error = pyqtSignal(int, str)

    def __init__(self, token, engine, demo=False, threshold=0.01, parent=None):
        super().__init__(parent)
        self.token, self.engine, self.demo = token, engine, demo
        self.threshold = threshold
        self.cancelled = threading.Event()
        self.finish_recording = threading.Event()

    def cancel(self):
        self.cancelled.set()
        self.finish_recording.set()

    def finish(self):
        self.finish_recording.set()

    def run(self):
        started = time.monotonic()
        stage = "initialization"
        diagnostics.event("voice.start", session=self.token, demo=self.demo, threshold=self.threshold)
        try:
            if self.demo:
                self.listening.emit(self.token)
                # Demo simulates listening; it does not open a microphone/model.
                self.finish_recording.wait(1.5)
                if not self.cancelled.is_set():
                    self.processing.emit(self.token)
                    self.recognized.emit(self.token, "Demo: arată două ținte.")
                return
            stage = "audio_import"
            import numpy as np
            import sounddevice as sd

            frames = round(SAMPLE_RATE * BLOCK_SECONDS)
            gate = SpeechGate(threshold=self.threshold)
            chunks = []
            stage = "microphone_open"
            with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1,
                                   dtype="float32", blocksize=frames) as stream:
                if self.cancelled.is_set():
                    return
                self.listening.emit(self.token)
                stage = "recording"
                diagnostics.event("voice.listening", session=self.token, sample_rate=SAMPLE_RATE)
                while not self.cancelled.is_set() and not self.finish_recording.is_set():
                    raw, overflowed = stream.read(frames)
                    if overflowed:
                        raise RuntimeError("audio_overflow")
                    chunk = np.frombuffer(raw, dtype=np.float32).copy()
                    chunks.append(chunk)
                    rms = float(np.sqrt(np.mean(chunk * chunk)))
                    if gate.observe(rms):
                        break
            diagnostics.event("voice.recording.finished", session=self.token,
                              audio_seconds=round(gate.elapsed, 2), detected_speech=gate.has_speech,
                              manual_stop=self.finish_recording.is_set(), cancelled=self.cancelled.is_set())
            if self.cancelled.is_set():
                return
            if not gate.has_speech or not chunks:
                self.error.emit(self.token, "no_speech")
                return
            self.processing.emit(self.token)
            stage = "transcription"
            diagnostics.event("voice.transcription.start", session=self.token)
            text = self.engine.transcribe(np.concatenate(chunks), self.cancelled)
            if not self.cancelled.is_set():
                if text:
                    diagnostics.protect(text)
                    diagnostics.event("voice.transcription.ready", session=self.token,
                                      characters=len(text), elapsed_seconds=round(time.monotonic() - started, 2))
                    self.recognized.emit(self.token, text)
                else:
                    self.error.emit(self.token, "no_speech")
        except Exception as error:
            if not self.cancelled.is_set():
                diagnostics.exception("voice.error", error, session=self.token, stage=stage,
                                      elapsed_seconds=round(time.monotonic() - started, 2))
                self.error.emit(self.token, "voice." + stage)
