import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.ai.openrouter import OpenRouterProvider, build_payload, decode_response, failure_details
from jarvis.features.callouts.model import VisualKind, VisualPlan
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.infrastructure.app_log import AppLog
from test_interaction import FakeVoice, FakeCapture
from jarvis.features.interaction.controller import InteractionController


class FakeProvider(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str)
    diagnostic = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sent = []
        self.cancelled = 0

    def send(self, request, visuals):
        self.sent.append((request, visuals))

    def cancel(self):
        self.cancelled += 1


class AiPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = DesktopController(self.app, provider_factory=FakeProvider,
            log=AppLog(Path(self.temp.name)/'app.log'))
        screen = self.app.primaryScreen()
        r = screen.geometry()
        self.frame = ScreenFrame('actual-context-id', 'now', ScreenGeometry(screen.name(), r.x(), r.y(),
            r.width(), r.height(), r.width(), r.height(), screen.devicePixelRatio()), b'png-test-bytes')

    def tearDown(self):
        self.controller.close()
        self.controller.deleteLater()
        self.temp.cleanup()

    def test_voice_only_runtime_does_not_construct_manual_interface(self):
        c = self.controller
        c.voice_only = True
        c.enable_voice = True
        c.voice_factory = FakeVoice
        signals = FakeVoice()
        c.hotkey_factory = lambda *_: SimpleNamespace(
            pressed=signals.ready, released=signals.ready, start=Mock(), close=Mock())
        c.tray_factory = Mock(return_value=SimpleNamespace(menu=Mock(), set_status=Mock(), close=Mock()))
        with patch('jarvis.app.MainWindow') as window, patch('jarvis.app.SingleInstance') as instance:
            instance.return_value.is_primary = True
            self.assertTrue(c.start())
            window.assert_not_called()
            self.assertIsNone(c.window)
            self.assertIsNone(c.tray_factory.call_args.args[0])
            c._hide_for_voice_capture()
            c._restore_after_voice_capture()
            c._voice_failed('Test microphone notice')
            c.session.set_frame(self.frame)
            request = c.session.begin('Te rog arată-mi cum să închid browserul.')
            c._voice_prepared(request)
            context = json.loads(build_payload(request, (), 'model')['messages'][1]['content'][0]['text'])
            self.assertEqual(context['visual_intent'], 'guide')
            self.assertNotIn('mode', context)
            c.end_session()

    def test_complete_explanation_reaches_the_only_visible_bubble(self):
        from jarvis.features.interaction.intent import VisualIntent
        answer = 'E este energia, m este masa. Masa are energie chiar și în repaus. Exemplu: dublarea masei dublează energia.'
        for intent in (VisualIntent.EXPLAIN, VisualIntent.AUTO):
            plan = VisualPlan.parse({'text': answer, 'actions': [
                {'type': 'callout', 'id': 'formula', 'text': 'Echivalența masei și energiei.',
                 'target': [.3, .3, .5, .4], 'target_text': 'E=mc²', 'target_confidence': .95}]},
                intent=intent, require_grounding=True)
            self.assertEqual(plan.actions[0].text, answer)
            self.assertEqual(plan.actions[0].target, (.3, .3, .5, .4))

    def test_hold_release_context_provider_response_overlay_and_followup(self):
        c = self.controller
        voice, capture = FakeVoice(), FakeCapture()
        interaction = InteractionController(c.session, voice, capture=capture)
        interaction.prepared.connect(c._submit_ai)
        try:
            interaction.press(self.app.primaryScreen())
            voice.listening.emit(interaction.token)
            capture.pending = False
            capture.frame_changed.emit(self.frame)
            capture.finished.emit()
            interaction.release()
            voice.stopped.emit(interaction.token)
            voice.transcribed.emit(interaction.token, 'Explică ecuația.')
            request, visuals = c.provider.sent[-1]
            payload = build_payload(request, visuals, 'model')
            self.assertIn('cG5nLXRlc3QtYnl0ZXM=', payload['messages'][1]['content'][1]['image_url']['url'])
            self.assertIn('Explică ecuația.', payload['messages'][1]['content'][0]['text'])
            c.provider.succeeded.emit(request.id, {'text': 'Scădem trei.', 'actions': [
                {'type': 'callout', 'id': 'step-1', 'text': 'Scădem 3.', 'target': [.3, .3, .5, .4],
                 'target_text': 'x + 3 = 5', 'target_confidence': .95},
                {'type': 'highlight', 'id': 'source', 'target': [.3, .3, .5, .4]}]})
            self.assertEqual(len(c.overlay.callouts), 1)
            self.assertEqual(len(c.overlay.annotations), 0)  # Explanation allows callouts only.
            self.assertFalse(c._ai_progress.isActive())
            followup = c.session.begin('De ce?')
            c._submit_ai(followup)
            self.assertEqual(followup.history[-1].explanation, 'Scădem trei.')
            self.assertEqual(c.provider.sent[-1][1][0]['id'], 'step-1')
        finally:
            interaction.close()

    def test_cancel_timeout_end_and_late_response(self):
        c = self.controller
        c.session.set_frame(self.frame)
        request = c.session.begin('Întrebare')
        c._submit_ai(request)
        c._ai_timeout()
        self.assertIsNone(c._ai_pending)
        self.assertIn('așteptare', c.session.turns[-1].notice)
        c.provider.succeeded.emit(request.id, {'text': 'Late', 'actions': []})
        self.assertIsNone(c.session.turns[-1].explanation)
        request = c.session.begin('Alta')
        c._submit_ai(request)
        c.end_session()
        c.provider.succeeded.emit(request.id, {'text': 'Late', 'actions': []})
        self.assertEqual(c.session.turns, ())
        self.assertIsNone(c.overlay)

    def test_missing_key_does_not_send_network(self):
        provider = OpenRouterProvider()
        errors = []
        provider.failed.connect(lambda _, text: errors.append(text))
        request = self.controller.session.begin('Test')
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}):
            provider.send(request)
        self.assertIsNone(provider.reply)
        self.assertIn('.env', errors[0])

    def test_decode_keeps_text_despite_invalid_visuals(self):
        payload = {'text': 'Valid answer', 'actions': [{'type': 'unknown'}, {'type': 'none'}]}
        raw = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(payload)}}]})
        decoded = decode_response(raw)
        plan = VisualPlan.parse(decoded)
        self.assertEqual(plan.text, 'Valid answer')
        self.assertEqual(plan.actions[0].kind, VisualKind.NONE)
        with self.assertRaises(ValueError):
            decode_response(raw.replace('"stop"', '"length"'))

    def test_provider_schema_error_is_specific_without_reflecting_sensitive_body(self):
        raw = b'{"error":{"metadata":{"raw":"schema has too many states; secret-key; transcript"}}}'
        reason, message = failure_details(400, raw)
        self.assertEqual(reason, 'schema_complexity')
        self.assertIn('400', message)
        self.assertNotIn('secret-key', message)
        self.assertNotIn('transcript', message)
        self.controller.provider.diagnostic.emit('request-test', 'http_status=400; reason=schema_complexity')
        log = (Path(self.temp.name)/'app.log').read_text(encoding='utf-8')
        self.assertIn('reason=schema_complexity', log)
        self.assertNotIn('secret-key', log)
        self.assertEqual(failure_details(None, b'')[0], 'network')
        self.assertIn('413', failure_details(413, b'')[1])

    def test_http_400_completion_emits_safe_diagnostic_and_releases_reply(self):
        provider = OpenRouterProvider()
        reply = Mock()
        reply.attribute.return_value = 400
        reply.readAll.return_value = b'{"error":"too many states; private prompt; secret-key"}'
        reply.error.return_value = SimpleNamespace(name='ProtocolInvalidOperationError')
        provider.reply = reply
        failures, diagnostics = [], []
        provider.failed.connect(lambda _, message: failures.append(message))
        provider.diagnostic.connect(lambda _, details: diagnostics.append(details))
        provider._finished('request', reply)
        self.assertIsNone(provider.reply)
        reply.deleteLater.assert_called_once()
        self.assertEqual(len(failures), 1)
        self.assertIn('schemă prea complexă', failures[0])
        self.assertIn('http_status=400', diagnostics[0])
        self.assertNotIn('private prompt', str(failures + diagnostics))
        self.assertNotIn('secret-key', str(failures + diagnostics))
