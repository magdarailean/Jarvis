import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.ai.openrouter import OpenRouterProvider, build_payload, decode_response
from jarvis.features.callouts.model import VisualKind, VisualPlan
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.infrastructure.app_log import AppLog
from test_interaction import FakeVoice, FakeCapture
from jarvis.features.interaction.controller import InteractionController


class FakeProvider(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str)

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
                {'type': 'callout', 'id': 'step-1', 'text': 'Scădem 3.', 'target': [.3, .3, .5, .4]},
                {'type': 'highlight', 'id': 'source', 'target': [.3, .3, .5, .4]}]})
            self.assertEqual(len(c.overlay.callouts), 1)
            self.assertEqual(len(c.overlay.annotations), 1)
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
