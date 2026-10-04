import importlib.util
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import create_application
from jarvis.features.voice_input.ion_adapter import IonAdapter
from jarvis.features.voice_input.ion_worker import RecordingControl, load_ion, SpeechOnlyModel


class AdapterTests(unittest.TestCase):
    def test_speech_filter_preserves_romanian_decoder_options(self):
        model = Mock()
        wrapper = SpeechOnlyModel(model)
        wrapper.transcribe('audio', language='ro', beam_size=5, temperature=0.0)
        model.transcribe.assert_called_once_with('audio', language='ro', beam_size=5,
            temperature=0.0, vad_filter=True, condition_on_previous_text=False)

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def wait_until(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertTrue(condition())

    def test_real_subprocess_transport_start_stop_text_and_close(self):
        fixture = Path(__file__).with_name("ion_fixture.py").resolve()
        with patch.dict(os.environ, {"JARVIS_ION_SOURCE": str(fixture)}):
            adapter = IonAdapter()
            errors, transcripts, listening, stopped = [], [], [], []
            adapter.failed.connect(errors.append)
            adapter.listening.connect(listening.append)
            adapter.stopped.connect(stopped.append)
            adapter.transcribed.connect(lambda token, text: transcripts.append((token, text)))
            try:
                adapter.warmup()
                self.wait_until(lambda: adapter.available or errors)
                self.assertEqual(errors, [])
                adapter.start(7)
                self.wait_until(lambda: listening == [7])
                QTest.qWait(200)
                adapter.stop()
                self.wait_until(lambda: bool(transcripts) or errors)
                self.assertEqual(errors, [])
                self.assertEqual(stopped, [7])
                self.assertEqual(transcripts, [(7, "Explică-mi exercițiul.")])
                adapter.start(8)
                self.wait_until(lambda: listening == [7, 8])
                adapter.close()
                QTest.qWait(50)
                self.assertEqual(len(transcripts), 1)
                self.assertFalse(adapter.available)
            finally:
                adapter.close()
                adapter.deleteLater()

    def test_missing_ion_source_reports_failure_without_crashing(self):
        with patch.dict(os.environ, {"JARVIS_ION_SOURCE": str(Path("missing-ion.py").resolve())}):
            adapter = IonAdapter()
            errors = []
            adapter.failed.connect(errors.append)
            try:
                adapter.warmup()
                self.wait_until(lambda: bool(errors))
                self.assertFalse(adapter.available)
                self.assertFalse(adapter.timer.isActive())
            finally:
                adapter.close()
                adapter.deleteLater()

    @unittest.skipUnless(importlib.util.find_spec("faster_whisper"), "Install .[voice] for Ion contract check")
    def test_actual_readonly_ion_functions_with_fake_device_and_model(self):
        import numpy as np
        source = Path(__file__).resolve().parents[1] / "CursorMain" / "workingVersion1.py"
        original = source.read_bytes()
        ion = load_ion(source)
        done, started = threading.Event(), threading.Event()
        device = SimpleNamespace(rec=Mock(return_value=np.zeros((160000, 1), dtype="float32")),
                                 wait=lambda: done.wait(3), stop=done.set)
        adapter = RecordingControl(device, started.set)
        ion.sd = adapter
        audio = []
        job = threading.Thread(target=lambda: audio.append(ion.record_voice()))
        try:
            job.start()
            self.assertTrue(started.wait(2))
            adapter.stop()
            job.join(3)
            self.assertFalse(job.is_alive())
            self.assertEqual(audio[0].shape, (160000,))
            device.rec.assert_called_once_with(frames=160000, samplerate=16000, channels=1, dtype="float32")
            model = SimpleNamespace(transcribe=Mock(return_value=(iter([
                SimpleNamespace(text=" Explică-mi "), SimpleNamespace(text=" problema. ")]), None)))
            self.assertEqual(ion.transcribe_voice(model, audio[0]), "Explică-mi problema.")
            self.assertEqual(model.transcribe.call_args.kwargs,
                             dict(language="ro", task="transcribe", beam_size=5, temperature=0.0))
            self.assertEqual(source.read_bytes(), original)
        finally:
            adapter.stop()
            job.join(3)
