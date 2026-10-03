import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import tempfile
import unittest
import uuid

from PySide6.QtCore import QBuffer, QIODevice, QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.hotkey.windows import GlobalHotkey, parse_shortcut
from jarvis.features.interaction.controller import InteractionController
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.features.session import Session
from jarvis.infrastructure.app_log import AppLog


def frame():
    return ScreenFrame("fixture", "now", ScreenGeometry("test", 0, 0, 100, 100, 100, 100, 1), b"fixture")


class FakeVoice(QObject):
    ready = Signal()
    listening = Signal(int)
    stopped = Signal(int)
    transcribed = Signal(int, str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.available = True
        self.starts = []
        self.stops = self.closes = 0

    def warmup(self):
        self.available = True
        self.ready.emit()

    def start(self, token):
        self.starts.append(token)

    def stop(self):
        self.stops += 1

    def close(self):
        self.closes += 1
        self.available = False


class FakeCapture(QObject):
    frame_changed = Signal(object)
    finished = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.pending = False
        self.calls = 0

    def begin(self, screen, delay_ms=0):
        self.calls += 1
        self.pending = True
        self.frame_changed.emit(None)

    def deliver(self):
        self.pending = False
        self.frame_changed.emit(frame())
        self.finished.emit()

    def clear(self, **kwargs):
        self.pending = False
        self.frame_changed.emit(None)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.session = Session()
        self.voice = FakeVoice()
        self.capture = FakeCapture()
        self.pipeline = InteractionController(self.session, self.voice, capture=self.capture)
        self.states = []
        self.contexts = []
        self.pipeline.state_changed.connect(lambda text, mic: self.states.append((text, mic)))
        self.pipeline.prepared.connect(self.contexts.append)

    def tearDown(self):
        self.pipeline.close()

    def activate(self):
        self.pipeline.press(self.app.primaryScreen())
        token = self.voice.starts[-1]
        self.voice.listening.emit(token)
        return token

    def test_hold_capture_release_transcript_reaches_ai_boundary_once(self):
        token = self.activate()
        self.pipeline.press(self.app.primaryScreen())
        self.assertEqual(len(self.voice.starts), 1)
        self.assertEqual(self.capture.calls, 1)
        self.assertIn(("Ascult...", True), self.states)
        self.capture.deliver()
        self.pipeline.release()
        self.pipeline.release()
        self.assertEqual(self.voice.stops, 1)
        self.voice.stopped.emit(token)
        self.voice.transcribed.emit(token, "Explică-mi problema aceasta.")
        self.assertEqual(len(self.contexts), 1)
        self.assertEqual(self.contexts[0].question, "Explică-mi problema aceasta.")
        self.assertEqual(self.contexts[0].frame.id, "fixture")
        self.assertIs(self.session.pending, self.contexts[0])
        self.assertIn(("Procesez...", False), self.states)
        self.assertEqual(self.states[-1], ("Context pregătit · AI neconectat", False))
        self.voice.transcribed.emit(token, "duplicate")
        self.assertEqual(len(self.contexts), 1)

    def test_transcript_can_arrive_before_capture_and_old_results_are_ignored(self):
        token = self.activate()
        self.pipeline.release()
        self.voice.transcribed.emit(token, "Întrebare")
        self.assertEqual(self.contexts, [])
        self.capture.deliver()
        self.assertEqual(len(self.contexts), 1)
        self.pipeline.reset()
        self.assertIsNone(self.pipeline.context)
        self.assertIsNone(self.session.frame)
        self.voice.transcribed.emit(token, "stale")
        self.assertEqual(len(self.contexts), 1)

    def test_silence_failure_and_display_invalidation_stop_recording(self):
        token = self.activate()
        self.capture.deliver()
        self.voice.transcribed.emit(token, "   ")
        self.assertFalse(self.pipeline.active)
        self.assertIsNone(self.pipeline.context)
        self.assertEqual(self.voice.closes, 1)
        self.voice.warmup()
        self.activate()
        self.capture.deliver()
        self.capture.frame_changed.emit(None)
        self.assertFalse(self.pipeline.active)
        self.assertEqual(self.voice.closes, 2)
        self.assertIsNone(self.session.frame)

    def test_release_before_worker_starts_does_not_capture(self):
        self.pipeline.press(self.app.primaryScreen())
        token = self.voice.starts[-1]
        self.pipeline.release()
        self.voice.listening.emit(token)
        self.voice.transcribed.emit(token, "")
        self.assertEqual(self.capture.calls, 0)
        self.assertEqual(self.contexts, [])
        self.assertFalse(self.pipeline.active)

    def test_unconfigured_voice_does_not_start_capture_or_recording(self):
        self.voice.available = False
        self.pipeline.press(self.app.primaryScreen())
        self.assertFalse(self.pipeline.active)
        self.assertEqual(self.voice.starts, [])
        self.assertEqual(self.capture.calls, 0)


class HotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def test_parse_and_native_registration_conflict_cleanup(self):
        self.assertEqual(parse_shortcut("Ctrl+Shift+Space"), (6, 32, (17, 16, 32)))
        for invalid in ("Space", "Ctrl+Ctrl+A", "Ctrl+F25", "Ctrl+Nope"):
            with self.assertRaises(ValueError):
                parse_shortcut(invalid)
        first = GlobalHotkey(self.app, "Ctrl+Shift+F24")
        second = GlobalHotkey(self.app, "Ctrl+Shift+F24")
        second.ID += 1
        try:
            first.start()
            with self.assertRaises(OSError):
                second.start()
            presses, releases = [], []
            first.pressed.connect(lambda: presses.append(True))
            first.released.connect(lambda: releases.append(True))
            with patch.object(first, "down", return_value=True):
                # Post the real thread message so Qt's native event filter is exercised.
                native = ctypes.windll.user32
                native.PostThreadMessageW.argtypes = [ctypes.c_uint32, ctypes.c_uint32,
                                                      ctypes.c_size_t, ctypes.c_ssize_t]
                self.assertTrue(native.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(),
                                                         0x0312, first.ID, 0))
                QTest.qWait(40)
                self.assertEqual(len(presses), 1)
                first.activate()
                first.check_release()
            with patch.object(first, "down", return_value=False):
                first.check_release()
                first.check_release()
            self.assertEqual((len(presses), len(releases)), (1, 1))
            self.assertFalse(first.timer.isActive())
            first.close()
            second.start()
        finally:
            first.close()
            second.close()


class BackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def test_background_start_and_shutdown_never_show_main_window(self):
        with tempfile.TemporaryDirectory() as directory:
            hotkey = SimpleNamespace(start=Mock(), close=Mock())
            # Keep QObject signal owners alive through explicit local variables.
            pressed, released = FakeVoice(), FakeVoice()
            hotkey.pressed, hotkey.released = pressed.ready, released.ready
            controller = DesktopController(self.app, instance_key=f"Jarvis.Background.{uuid.uuid4().hex}",
                log=AppLog(Path(directory) / "app.log"), enable_voice=True, background=True,
                voice_factory=FakeVoice, hotkey_factory=lambda *_: hotkey)
            try:
                controller.start()
                self.assertFalse(controller.window.isVisible())
                pressed.ready.emit()
                self.assertTrue(controller.interaction.active)
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap = QPixmap(100, 100)
                pixmap.fill()
                pixmap.save(buffer, "PNG")
                captured = ScreenFrame("background", "now", frame().geometry, bytes(buffer.data()))
                buffer.close()
                controller.interaction.capture._capture = Mock(return_value=captured)
                token = controller.interaction.token
                controller.interaction.voice.listening.emit(token)
                QTest.qWait(150)
                released.ready.emit()
                self.assertFalse(controller.interaction.held)
                controller.interaction.voice.stopped.emit(token)
                controller.interaction.voice.transcribed.emit(token, "Explică-mi problema.")
                self.assertIsNotNone(controller.interaction.context)
                self.assertFalse(controller.window.isVisible())
                controller.window.capture_clear_button.click()
                self.assertIsNone(controller.interaction.context)
                self.assertIsNone(controller.session.frame)
                self.assertTrue(controller.window.capture_preview.pixmap().isNull())
                controller.end_session()
                self.assertFalse(controller.interaction.active)
                self.assertIsNone(controller.interaction.context)
                self.assertFalse(controller.window.isVisible())
            finally:
                controller.close()
                self.assertFalse(controller.window.isVisible())
                hotkey.close.assert_called_once()
                controller.deleteLater()
                QTest.qWait(20)
