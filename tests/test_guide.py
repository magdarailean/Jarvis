import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from jarvis.app import DesktopController, create_application
from jarvis.features.ai.openrouter import build_payload
from jarvis.features.interaction.guide import GuideSession
from jarvis.features.interaction.intent import VisualIntent
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.infrastructure.app_log import AppLog
from test_ai_pipeline import FakeProvider


def answer(status="next", **extra):
    return {"text": "Deschide folderul cu documentul.", "guide_status": status,
            "completion_evidence": "Documentul este deschis în Word." if status == "complete" else "",
            "actions": [{"type": "pointer/cursor", "id": "next", "target": [.2,.2,.3,.3],
                         "target_text": "Documente", "target_confidence": .98}] if status == "next" else [], **extra}


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.c = DesktopController(self.app, provider_factory=FakeProvider,
            log=AppLog(Path(self.temp.name)/"log"))
        self.c.pointer_bridge.show = Mock()
        self.c.pointer_bridge.hide = Mock()
        self.c.indicator = Mock()
        self.c.guide.buttons = lambda: False
        screen = self.app.primaryScreen()
        rect = screen.geometry()
        self.frame = ScreenFrame("screen", "now", ScreenGeometry(screen.name(), rect.x(), rect.y(),
            rect.width(), rect.height(), rect.width(), rect.height(), screen.devicePixelRatio()), b"image")
        self.goal = "Arată-mi cum să deschid un fișier DOCX."

    def tearDown(self):
        self.c.close()
        self.c.deleteLater()
        self.temp.cleanup()

    def start(self):
        self.c.session.set_frame(self.frame)
        self.c._voice_prepared(self.c.session.begin(self.goal))
        return self.c.provider.sent[-1][0]

    def test_multiple_steps_keep_goal_and_finish_only_with_evidence(self):
        first = self.start()
        self.c.provider.succeeded.emit(first.id, answer())
        self.assertTrue(self.c.guide.active)
        self.c.pointer_bridge.show.assert_called_once()
        self.c._guide_input()  # A click anywhere, including the wrong control.
        self.c.pointer_bridge.hide.assert_called()
        self.c._guide_frame(self.frame)
        second = self.c.provider.sent[-1][0]
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(second.question, self.goal)
        self.assertEqual(second.visual_intent, VisualIntent.GUIDE)
        self.assertTrue(second.guide_context["screen_unchanged"])
        self.assertEqual(second.guide_context["previous_step"], answer()["text"])
        self.c.provider.succeeded.emit(second.id, answer())  # May legitimately repeat target.
        self.assertEqual(self.c.pointer_bridge.show.call_count, 2)
        self.c._guide_input()
        self.c._guide_frame(self.frame)
        third = self.c.provider.sent[-1][0]
        self.c.provider.succeeded.emit(third.id, answer("complete"))
        self.assertFalse(self.c.guide.active)
        self.assertFalse(self.c.guide.poll.isActive())
        self.assertEqual(self.c.indicator.display.call_args.args[0], "Gata")

    def test_click_cancels_old_response_and_debounces_double_click(self):
        first = self.start()
        self.c.guide.buttons = lambda: True
        self.c.guide.sample()
        self.assertIsNone(self.c._ai_pending)
        self.c.provider.succeeded.emit(first.id, answer())
        self.c.pointer_bridge.show.assert_not_called()
        self.c.guide.buttons = lambda: False
        self.c.guide.sample()
        self.assertTrue(self.c.guide.settle.isActive())
        self.c.guide.buttons = lambda: True
        self.c.guide.sample()
        self.assertFalse(self.c.guide.settle.isActive())
        self.c.guide.buttons = lambda: False
        self.c.guide.sample()
        with patch.object(self.c.guide_capture, 'begin') as capture:
            self.c.guide.inspect.emit()
            capture.assert_called_once()
            self.assertEqual(capture.call_args.kwargs['delay_ms'], 100)

    def test_wait_retries_are_bounded_and_do_not_claim_completion(self):
        request = self.start()
        for _ in range(4):
            self.c.provider.succeeded.emit(request.id, answer("wait"))
            if self.c.guide.settle.isActive():
                self.c.guide.settle.stop()
                self.c._guide_frame(self.frame)
                request = self.c.provider.sent[-1][0]
        self.assertTrue(self.c.guide.active)
        self.assertFalse(self.c.guide.settle.isActive())
        self.assertIn("Ghidare în așteptare", self.c.indicator.display.call_args.args[0])

    def test_invalid_target_and_false_completion_pause_safely(self):
        for payload in (answer("complete", completion_evidence=""),
                        answer(actions=[{"type":"pointer/cursor", "id":"bad", "target":[999,0,1,1]}]),
                        answer("complete", actions=answer()["actions"])):
            request = self.start()
            self.c.provider.succeeded.emit(request.id, payload)
            self.assertTrue(self.c.guide.active)
            self.assertIn("Ghidare în așteptare", self.c.indicator.display.call_args.args[0])
            self.c._guide_stop()
        self.c.pointer_bridge.show.assert_not_called()

    def test_new_voice_request_pauses_sequence_and_cancels_old_response(self):
        request = self.start()
        self.c.interaction = Mock(active=False)
        self.c._push_to_talk()
        self.assertTrue(self.c.guide.active)
        self.assertFalse(self.c.guide.poll.isActive())
        self.c.provider.succeeded.emit(request.id, answer())
        self.c.pointer_bridge.show.assert_not_called()
        self.c.interaction.press.assert_called_once()

    def test_voice_followup_keeps_guide_and_rejects_bubbles(self):
        first = self.start()
        self.c.provider.succeeded.emit(first.id, answer())
        self.c.interaction = Mock(active=False)
        self.c._push_to_talk()
        self.c.session.set_frame(self.frame)
        self.c._voice_prepared(self.c.session.begin('Și acum?'))
        request = self.c.provider.sent[-1][0]
        self.assertEqual(request.visual_intent, VisualIntent.GUIDE)
        self.assertEqual(self.c.session.pending.visual_intent, VisualIntent.GUIDE)
        self.assertEqual(request.guide_context['original_goal'], self.goal)
        self.assertTrue(self.c.guide.poll.isActive())
        payload = answer(actions=[dict(type='callout', id='bad', text='Do not show')])
        self.c.provider.succeeded.emit(request.id, payload)
        self.assertEqual(self.c.overlay.callouts, ())
        self.assertTrue(self.c.guide.active)
        self.c.session.set_frame(self.frame)
        self.c._voice_prepared(self.c.session.begin('Explică-mi ce înseamnă acest buton.'))
        request = self.c.provider.sent[-1][0]
        self.assertEqual(request.visual_intent, VisualIntent.EXPLAIN)
        self.assertFalse(self.c.guide.active)

    def test_mixed_request_prioritizes_guide_in_real_controller(self):
        self.goal = 'Arată-mi unde să apăs și explică-mi ce face butonul.'
        request = self.start()
        self.assertEqual(request.visual_intent, VisualIntent.GUIDE)
        self.c.provider.succeeded.emit(request.id, answer())
        self.c.pointer_bridge.show.assert_called_once()
        self.assertEqual(self.c.overlay.callouts, ())

    def test_canva_creation_is_pointer_only_and_continues_after_click(self):
        self.goal = 'Ajuta-ma cum sa fac o prezentare in canva.'
        first = self.start()
        self.assertEqual(first.visual_intent, VisualIntent.GUIDE)
        payload = build_payload(first, [], 'model')
        types = payload['response_format']['json_schema']['schema']['properties']['actions']['items']['properties']['type']['enum']
        self.assertEqual(types, ['pointer/cursor'])
        self.c.provider.succeeded.emit(first.id, answer(text='Apasă Prezentare.'))
        self.c.pointer_bridge.show.assert_called_once()
        self.assertEqual(self.c.overlay.callouts, ())
        self.c._guide_input()
        self.c._guide_frame(self.frame)
        second = self.c.provider.sent[-1][0]
        self.assertEqual(second.guide_context['original_goal'], self.goal)
        self.assertEqual(second.visual_intent, VisualIntent.GUIDE)
        self.c.provider.succeeded.emit(second.id, answer(actions=[
            dict(type='callout', id='wrong', text='Alege un șablon.')]))
        self.assertEqual(self.c.overlay.callouts, ())
        self.assertTrue(self.c.guide.active)

    def test_guide_schema_and_context_prohibit_mode_switch(self):
        request = self.start()
        payload = build_payload(request, [], "model")
        schema = payload['response_format']['json_schema']['schema']
        self.assertIn('guide_status', schema['required'])
        self.assertEqual(schema['properties']['actions']['maxItems'], 1)
        self.assertEqual(schema['properties']['actions']['items']['properties']['type']['enum'], ['pointer/cursor'])
        context = json.loads(payload['messages'][1]['content'][0]['text'])
        self.assertEqual(context['guide_session']['original_goal'], self.goal)

    def test_auto_selected_pointer_locks_followups_to_guide(self):
        self.c.session.set_frame(self.frame)
        request = self.c.session.begin("Ajută-mă cu documentul.")
        self.c._submit_ai(request)
        payload = answer()
        del payload['guide_status']
        self.c.provider.succeeded.emit(request.id, payload)
        self.assertTrue(self.c.guide.active)
        self.c._guide_frame(self.frame)
        followup = self.c.provider.sent[-1][0]
        self.assertEqual(followup.visual_intent, VisualIntent.GUIDE)
        self.assertEqual(followup.question, request.question)

    def test_provider_failure_stops_observer(self):
        request = self.start()
        self.c.provider.failed.emit(request.id, "Network failure")
        self.assertFalse(self.c.guide.active)
        self.assertFalse(self.c.guide.settle.isActive())
