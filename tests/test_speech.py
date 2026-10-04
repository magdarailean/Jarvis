from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal, QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.speech.service import SpeechService
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.infrastructure.app_log import AppLog
from test_ai_pipeline import FakeProvider
from test_guide import answer


class FakeSpeech(QObject):
    preparing = Signal()
    started = Signal()
    finished = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.busy = False
        self.texts = []

    def say(self, text):
        self.busy = True
        self.texts.append(text)
        self.preparing.emit()

    def stop(self):
        self.busy = False

    close = stop


class SpokenAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.c = DesktopController(self.app, provider_factory=FakeProvider, speech_factory=FakeSpeech,
            log=AppLog(Path(self.temp.name)/'test.log'))
        self.c._speech_enabled = True
        self.c.indicator = Mock()
        self.c.pointer_bridge.show = Mock()
        self.c.pointer_bridge.hide = Mock()
        screen = self.app.primaryScreen()
        rect = screen.geometry()
        self.frame = ScreenFrame('screen', 'now', ScreenGeometry(screen.name(), rect.x(), rect.y(),
            rect.width(), rect.height(), rect.width(), rect.height(), screen.devicePixelRatio()), b'image')
        self.c.session.set_frame(self.frame)

    def tearDown(self):
        self.c.close()
        self.c.deleteLater()
        self.temp.cleanup()

    def explain(self):
        request = self.c.session.begin('Explică ecuația.')
        self.c._submit_ai(request)
        self.c.provider.succeeded.emit(request.id, {'text': 'Scădem trei din ambele părți.', 'actions': [
            {'type': 'callout', 'id': 'one', 'text': 'Scădem 3.', 'target': [.3,.3,.5,.4],
             'target_text': 'x + 3 = 7', 'target_confidence': .98}]})

    def test_speech_uses_visible_bubble_text_not_full_answer(self):
        self.explain()
        self.assertEqual(self.c.speech.texts, [self.c.overlay.callouts[0].text])
        self.assertEqual(self.c.speech.texts, ['Scădem trei din ambele părți.'])

    def test_multiple_callouts_follow_render_order_and_skip_overflow(self):
        request = self.c.session.begin('Explică ecuația.')
        self.c._submit_ai(request)
        actions = [dict(type='callout', id=str(i), text=text,
                        target=target, target_text='ecuație', target_confidence=.98)
                   for i, (text, target) in enumerate([
                       ('Primul pas.', [.1,.2,.2,.3]),
                       ('Al doilea pas.', [.7,.6,.8,.7]),
                       ('Nu încape.', [.4,.4,.5,.5])])]
        self.c.provider.succeeded.emit(request.id, dict(text='Răspuns separat lung.', actions=actions))
        displayed = [item.text for item, _ in self.c.overlay.displayed_callouts()]
        self.assertEqual(displayed, ['Primul pas.', 'Al doilea pas.'])
        self.assertEqual(self.c.speech.texts, ['\n\n'.join(displayed)])

    def test_no_callout_does_not_speak_separate_explanation(self):
        request = self.c.session.begin('Salut!')
        self.c._submit_ai(request)
        self.c.provider.succeeded.emit(request.id, dict(text='Răspuns fără bulă.', actions=[]))
        self.assertEqual(self.c.speech.texts, [])

    def test_speech_holds_bubble_then_expires_five_seconds_after_finish(self):
        self.explain()
        timing = self.c.overlay.callout_timing
        start, reveal, _, expires = timing.entries['one']
        self.assertIsNone(expires)
        timing.clock = lambda: start + 60
        timing.tick()
        self.assertEqual(len(self.c.overlay.callouts), 1)
        self.c.speech.started.emit()
        self.assertEqual(self.c._voice_status, 'Vorbesc...')
        self.c.speech.busy = False
        self.c.speech.finished.emit()
        self.assertEqual(self.c._voice_status, 'Gata')
        self.c.speech.failed.emit('Eroare simulată')
        timing.tick()
        self.assertEqual(len(self.c.overlay.callouts), 1)
        expires = start + 65
        self.assertEqual(timing.entries['one'][3], expires)
        timing.clock = lambda: expires-.01
        timing.tick()
        self.assertEqual(len(self.c.overlay.callouts), 1)
        self.assertEqual(len(self.c.session.turns), 1)
        timing.clock = lambda: expires+.01
        timing.tick()
        self.assertEqual(self.c.overlay.callouts, ())

    def test_failure_releases_hold_and_removed_bubble_is_safe(self):
        self.explain()
        timing = self.c.overlay.callout_timing
        start = timing.entries['one'][0]
        timing.clock = lambda: start+2
        self.c.speech.failed.emit('Eroare simulată')
        self.assertEqual(timing.entries['one'][3], start+7)
        self.c.overlay.remove('one')
        self.c.speech.finished.emit()
        self.assertEqual(timing.entries, {})

    def test_ptt_stops_speech_before_listening_and_keeps_history(self):
        self.explain()
        def press(*_):
            self.assertFalse(self.c.speech.busy)
            self.assertEqual(self.c.overlay.callouts, ())
            self.assertEqual(len(self.c.session.turns), 1)
        self.c.interaction = SimpleNamespace(active=False, press=Mock(side_effect=press), close=lambda: None)
        self.c._push_to_talk()
        self.c.interaction.press.assert_called_once()

    def test_guide_speaks_without_switching_to_callout(self):
        self.c.guide.buttons = lambda: False
        request = self.c.session.begin('Arată-mi cum să deschid un fișier DOCX.')
        self.c._voice_prepared(request)
        sent = self.c.provider.sent[-1][0]
        self.c.provider.succeeded.emit(sent.id, answer())
        self.assertEqual(self.c.speech.texts, [answer()['text']])
        self.c.pointer_bridge.show.assert_called_once()
        self.assertEqual(self.c.overlay.callouts, ())
        self.assertTrue(self.c.guide.active)

    def test_process_cancellation_rejects_late_events_and_next_speech_finishes(self):
        service = SpeechService()
        finished, errors = [], []
        service.finished.connect(lambda: finished.append(True))
        service.failed.connect(errors.append)
        real_start = QProcess.start
        script = "import sys,json,time; json.loads(sys.stdin.readline()); print(json.dumps(dict(event='started')),flush=True); time.sleep(.15)"
        def start(process, executable, args):
            return real_start(process, executable, ['-c', script])
        try:
            with patch.object(QProcess, 'start', start):
                service.say('Prima')
                QTest.qWait(70)
                old = service.process
                service.stop()
                service.say('A doua')
                self.assertIsNot(service.process, old)
                QTest.qWait(600)
            self.assertEqual(finished, [True])
            self.assertEqual(errors, [])
            self.assertFalse(service.busy)
        finally:
            service.close()
