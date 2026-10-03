"""Fake Ion contract for subprocess transport tests: no devices, models or network."""

import threading

SAMPLE_RATE = 16000


class WhisperModel:
    def __init__(self, *args, **kwargs):
        pass


class Device:
    def __init__(self):
        self.done = threading.Event()

    def rec(self, **kwargs):
        self.done.clear()
        return [0.0] * 160000

    def wait(self):
        self.done.wait(10)

    def stop(self):
        self.done.set()


sd = Device()


def record_voice():
    audio = sd.rec(frames=160000, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    return audio


def transcribe_voice(model, audio):
    return "Explică-mi exercițiul."
