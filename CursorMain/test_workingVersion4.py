"""OpenRouter checks using mocked HTTP; no microphone or desktop capture."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import time
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

import workingVersion4 as guide
from guidance_output_v4 import SpeechOutput, SpeechOutputRequest


DECISION = {
    "status": "action", "action": "click", "instruction": "Apasă butonul",
    "expected_result": "Se deschide meniul", "previous_result": "none",
    "target": {"left": .3, "top": .3, "right": .4, "bottom": .4},
}


def completion(content=None, finish_reason="stop"):
    return io.BytesIO(json.dumps({"choices": [{
        "finish_reason": finish_reason,
        "message": {"content": json.dumps(DECISION) if content is None else content},
    }]}).encode())


class OpenRouterTests(unittest.TestCase):
    def test_environment_key_takes_precedence(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
                patch.object(Path, "read_text", side_effect=AssertionError("No file read")):
            self.assertEqual(guide.load_api_key(), "test-key")

    def test_key_file_quotes_bom_and_invalid_assignment(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(guide, "BASE_DIR", Path(directory)), \
                patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            path = Path(directory) / "apikeyOpenRouter.txt"
            with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
                guide.load_api_key()
            path.write_text('KEY="test-key"\n', encoding="utf-8-sig")
            self.assertEqual(guide.load_api_key(), "test-key")
            path.write_text('OTHER="test-key"', encoding="utf-8")
            with self.assertRaises(ValueError):
                guide.load_api_key()

    def test_worker_sends_image_schema_and_emits_validated_decision(self):
        image = QImage(16, 16, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFF)
        worker = guide.AIRequest(7, image, {"original_goal": "Deschide meniul"},
                                 False, guide.DEFAULT_MODEL)
        decisions, errors = [], []
        worker.result.connect(lambda token, decision: decisions.append((token, decision)))
        worker.error.connect(lambda token, reason: errors.append((token, reason)))
        with patch.object(guide, "load_api_key", return_value="test-key"), \
                patch.object(guide, "urlopen", return_value=completion()) as transport:
            worker.run()
        self.assertFalse(errors)
        self.assertEqual(decisions[0][0], 7)
        self.assertEqual(decisions[0][1].target, guide.Target(.3, .3, .4, .4))
        request = transport.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, guide.OPENROUTER_URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(transport.call_args.kwargs["timeout"], 45.0)
        self.assertEqual(payload["model"], "google/gemini-2.5-flash-lite")
        self.assertEqual(payload["max_tokens"], 512)
        self.assertFalse(payload["reasoning"]["enabled"])
        self.assertTrue(payload["provider"]["require_parameters"])
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], guide.SCHEMA)
        image_url = payload["messages"][1]["content"][1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,/9j/"))

    def test_large_images_preserve_aspect_ratio_and_match_metadata(self):
        image = QImage(3840, 2160, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFF)
        worker = guide.AIRequest(7, image, {"screenshot": {"width": 3840, "height": 2160}},
                                 False, guide.DEFAULT_MODEL)
        with patch.object(guide, "load_api_key", return_value="test-key"), \
                patch.object(guide, "urlopen", return_value=completion()) as transport:
            worker.run()
        payload = json.loads(transport.call_args.args[0].data)
        content = payload["messages"][1]["content"]
        context = json.loads(content[0]["text"].removeprefix("Session:\n"))
        self.assertEqual((context["screenshot"]["width"], context["screenshot"]["height"]), (1280, 720))
        import base64
        sent_image = QImage.fromData(base64.b64decode(content[1]["image_url"]["url"].split(",")[1]))
        self.assertEqual((sent_image.width(), sent_image.height()), (1280, 720))

    def test_missing_truncated_and_error_responses_are_rejected(self):
        responses = [completion(finish_reason="length"), completion(content=""),
                     io.BytesIO(b'{"choices": []}'),
                     io.BytesIO(b'{"error": {"message": "private request data"}}')]
        for result in responses:
            with self.subTest(), patch.object(guide, "urlopen", return_value=result):
                with self.assertRaises(ValueError):
                    guide.request_openrouter("test-key", b"png", {}, guide.DEFAULT_MODEL)

    def test_authentication_error_emits_error_without_retry_or_decision(self):
        image = QImage(16, 16, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFF)
        worker = guide.AIRequest(8, image, {}, False, guide.DEFAULT_MODEL)
        errors, decisions = [], []
        worker.error.connect(lambda token, reason: errors.append((token, reason)))
        worker.result.connect(lambda *args: decisions.append(args))
        error = HTTPError(guide.OPENROUTER_URL, 401, "Unauthorized", {}, None)
        with patch.object(guide, "load_api_key", return_value="test-key"), \
                patch.object(guide, "urlopen", side_effect=error) as transport:
            worker.run()
        self.assertEqual(errors, [(8, "ai.api_request")])
        self.assertFalse(decisions)
        self.assertEqual(transport.call_count, 1)
        self.assertNotIn("test-key", guide.diagnostics.scrub("test-key"))

    def test_degenerate_rectangle_is_repaired_once_using_same_screenshot(self):
        for target in ({"left": .3, "top": .3, "right": .3, "bottom": .4},
                       {"left": .3, "top": .3, "right": .4, "bottom": .3},
                       {"left": .4, "top": .3, "right": .3, "bottom": .4}):
            with self.subTest(target=target):
                image = QImage(100, 100, QImage.Format.Format_RGB32)
                image.fill(0xFFFFFF)
                worker = guide.AIRequest(1, image, {"pending_attempt": None}, False, guide.DEFAULT_MODEL)
                decisions, errors = [], []
                worker.result.connect(lambda token, decision: decisions.append(decision))
                worker.error.connect(lambda token, reason: errors.append(reason))
                invalid = json.dumps(dict(DECISION, target=target))
                with patch.object(guide, "load_api_key", return_value="test-key"), \
                        patch.object(guide, "urlopen", side_effect=[completion(invalid), completion()]) as transport:
                    worker.run()
                self.assertFalse(errors)
                self.assertEqual(len(decisions), 1)
                self.assertEqual(decisions[0].target, guide.Target(.3, .3, .4, .4))
                self.assertEqual(transport.call_count, 2)
                first, second = [json.loads(call.args[0].data) for call in transport.call_args_list]
                self.assertEqual(first["messages"][1]["content"][1], second["messages"][1]["content"][1])
                context = json.loads(second["messages"][1]["content"][0]["text"].removeprefix("Session:\n"))
                self.assertIn("validation_feedback", context)
                self.assertIsNone(context["pending_attempt"])

    def test_failed_repair_stops_after_two_calls_and_emits_no_target(self):
        image = QImage(100, 100, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFF)
        worker = guide.AIRequest(1, image, {}, False, guide.DEFAULT_MODEL)
        decisions, errors = [], []
        worker.result.connect(lambda token, decision: decisions.append(decision))
        worker.error.connect(lambda token, reason: errors.append(reason))
        invalid = json.dumps(dict(DECISION, target={"left": .5, "top": .5, "right": .5, "bottom": .5}))
        with patch.object(guide, "load_api_key", return_value="test-key"), \
                patch.object(guide, "urlopen", side_effect=[completion(invalid), completion(invalid)]) as transport:
            worker.run()
        self.assertEqual(transport.call_count, 2)
        self.assertFalse(decisions)
        self.assertEqual(errors, ["ai.response_validation"])

    def test_cancelled_inflight_response_does_not_spend_a_repair_call(self):
        image = QImage(100, 100, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFF)
        worker = guide.AIRequest(1, image, {}, False, guide.DEFAULT_MODEL)
        decisions = []
        worker.result.connect(lambda token, decision: decisions.append(decision))
        invalid = json.dumps(dict(DECISION, target={"left": .5, "top": .5, "right": .5, "bottom": .5}))
        with patch.object(guide, "load_api_key", return_value="test-key"), \
                patch.object(guide, "urlopen", return_value=completion(invalid)) as transport, \
                patch.object(worker, "isInterruptionRequested", side_effect=[False, True]):
            worker.run()
        self.assertEqual(transport.call_count, 1)
        self.assertFalse(decisions)


class GuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.controller = guide.GuideController(demo=True, start_observer=False)
        self.controller.screen = self.app.primaryScreen()
        self.controller.physical_bounds = (0, 0, 2000, 1000)

    def tearDown(self):
        self.controller.cancel_session()
        self.controller.pointer.close()
        self.controller.caption.close()
        for timer in (self.controller.pointer.timer, self.controller.pointer.visual_timer):
            timer.stop()
        self.controller.deleteLater()
        self.app.processEvents()

    def test_voice_recognition_requests_new_capture_instead_of_old_image(self):
        with patch.object(self.controller, "begin_capture") as capture, \
                patch.object(self.controller, "dispatch_ai") as dispatch:
            self.controller.voice_recognized(self.controller.generation, "Deschide meniul")
        capture.assert_called_once_with("decision")
        dispatch.assert_not_called()

    def test_cropped_window_target_maps_to_monitor_and_click_verification(self):
        image = QImage(2000, 1000, QImage.Format.Format_RGB32)
        cropped, region = guide.crop_capture(image, (-2000, 0, 0, 1000), (-1500, 200, -500, 800))
        self.assertEqual((cropped.width(), cropped.height()), (1000, 600))
        self.assertEqual(region, guide.Target(.25, .2, .75, .8))
        mapped = guide.monitor_target(guide.Target(.4, .4, .6, .6), region)
        self.assertAlmostEqual(mapped.left, .45)
        self.assertAlmostEqual(mapped.top, .44)
        self.controller.capture_region = region
        decision = guide.Decision.parse(json.dumps(dict(DECISION, target={
            "left": .4, "top": .4, "right": .6, "bottom": .6})))
        with patch.object(self.controller.output, "say") as say:
            self.controller.accept_decision(self.controller.generation, decision)
        say.assert_called_once_with(decision.instruction)
        self.assertTrue(self.controller.caption.isVisible())
        self.controller.on_click(1000, 500, time.monotonic())
        self.assertEqual(self.controller.state, "settling")
        self.assertIsNotNone(self.controller.pending)
        self.assertFalse(self.controller.caption.isVisible())

    def test_caption_edges_click_through_and_plain_text(self):
        bounds = self.app.primaryScreen().availableGeometry()
        self.controller.caption.show_at("Apasă <Save> pentru a salva.", bounds.right(), bounds.bottom())
        self.assertTrue(bounds.contains(self.controller.caption.geometry()))
        self.assertTrue(self.controller.caption.windowFlags() & guide.Qt.WindowType.WindowTransparentForInput)
        self.assertEqual(self.controller.caption.textFormat(), guide.Qt.TextFormat.PlainText)
        self.assertIn("<Save>", self.controller.caption.text())
        pixel = self.controller.caption.grab().toImage().pixelColor(14, 14)
        self.assertEqual(pixel.name(), "#172033")

    def test_blocked_explanation_and_cancel_clear_caption_and_speech(self):
        decision = guide.Decision.parse(json.dumps(dict(DECISION, status="blocked", action="none",
                                                       target=None, instruction="Deschide aplicația mai întâi.")))
        with patch.object(self.controller.output, "say") as say:
            self.controller.accept_decision(self.controller.generation, decision)
        self.assertEqual(self.controller.state, "blocked")
        say.assert_called_once_with(decision.instruction)
        with patch.object(self.controller.output, "stop") as stop:
            self.controller.cancel_session()
        stop.assert_called_once()
        self.assertFalse(self.controller.caption.isVisible())

    def test_validation_failure_explanation_does_not_blame_capture(self):
        with patch.object(self.controller.output, "say") as say:
            self.controller.request_error(self.controller.generation, "ai.response_validation")
        text = say.call_args.args[0]
        self.assertIn("țintă validă", text)
        self.assertNotIn("Nu am putut verifica ecranul", text)

    def test_stale_result_cannot_show_caption_or_speak(self):
        token = self.controller.generation
        self.controller.cancel_session()
        with patch.object(self.controller.output, "say") as say:
            self.controller.accept_decision(token, guide.Decision.parse(json.dumps(DECISION)))
        say.assert_not_called()
        self.assertFalse(self.controller.caption.isVisible())

    def test_window_off_monitor_falls_back_to_whole_screen(self):
        image = QImage(2000, 1000, QImage.Format.Format_RGB32)
        _, region = guide.crop_capture(image, (0, 0, 2000, 1000), (2500, 0, 3000, 500))
        self.assertEqual(region, guide.Target(0, 0, 1, 1))

    def test_page_capture_waits_2500ms_and_restarts_after_another_click(self):
        self.controller.accept_decision(self.controller.generation,
                                        guide.Decision.parse(json.dumps(DECISION)))
        self.controller.on_click(700, 350, time.monotonic())
        self.assertEqual(self.controller.settle_timer.interval(), 2500)
        self.assertEqual(self.controller.settle_timer.timerType(), guide.Qt.TimerType.PreciseTimer)
        with patch.object(self.controller, "begin_capture") as capture:
            QTest.qWait(150)
            self.assertEqual(self.controller.state, "settling")
            capture.assert_not_called()
            self.controller.on_click(100, 100, time.monotonic())
            self.assertGreater(self.controller.settle_timer.remainingTime(), 2400)

    def test_workspace_create_completion_stops_timers_and_ignores_late_results(self):
        self.controller.goal = "Apasă Save Workspace, apoi Create"
        token = self.controller.generation
        create = guide.Decision.parse(json.dumps(dict(DECISION, instruction="Apasă Create.",
                                                       expected_result="Workspace creat")))
        self.controller.current = create
        self.controller.state = "waiting"
        self.controller.armed_at = 0
        self.controller.history = [{"action": "click", "instruction": "Apasă Save Workspace.",
                                    "verification": "succeeded"}]
        self.controller.on_click(700, 350, time.monotonic())
        complete = guide.Decision.parse(json.dumps(dict(DECISION, status="complete", action="none",
                                                        target=None, previous_result="succeeded",
                                                        instruction="Workspace-ul a fost creat.")))
        with patch.object(self.controller.output, "say") as say:
            self.controller.accept_decision(token, complete)
        say.assert_called_once_with(complete.instruction)
        self.assertEqual(self.controller.state, "idle")
        self.assertFalse(self.controller.goal)
        self.assertIsNone(self.controller.pending)
        self.assertFalse(self.controller.settle_timer.isActive())
        self.assertFalse(self.controller.capture_timer.isActive())
        self.assertFalse(self.controller.reminder_timer.isActive())
        with patch.object(self.controller, "begin_capture") as capture:
            self.controller.refresh()
            self.controller.on_click(700, 350, time.monotonic())
            self.controller.accept_decision(token, create)
        capture.assert_not_called()
        self.assertEqual(self.controller.state, "idle")

    def test_repeated_create_is_paused_without_claiming_completion(self):
        create = guide.Decision.parse(json.dumps(dict(DECISION, instruction="Apasă Create.")))
        record = dict(self.controller.action_data(create), verification="succeeded")
        self.controller.attempts = [record, record]
        self.controller.goal = "Creează workspace"
        with patch.object(self.controller.output, "say"):
            self.controller.accept_decision(self.controller.generation, create)
        self.assertEqual(self.controller.state, "blocked")
        self.assertIsNone(self.controller.current.target)
        self.assertEqual(self.controller.current.action, "none")
        self.assertFalse(self.controller.reminder_timer.isActive())
        self.assertTrue(self.controller.goal)
        self.controller.on_click(700, 350, time.monotonic())
        self.assertEqual(self.controller.state, "blocked")

    def test_alternating_cycle_is_paused_but_a_new_target_is_allowed(self):
        a = dict(DECISION)
        b = dict(DECISION, target={"left": .7, "top": .7, "right": .8, "bottom": .8})
        c = dict(DECISION, target={"left": .1, "top": .1, "right": .2, "bottom": .2})
        self.assertTrue(guide.repeating_click_cycle([a, b, a, b], a))
        self.assertFalse(guide.repeating_click_cycle([a, b, a, b], c))
        shifted = dict(a, target={"left": .302, "top": .302, "right": .402, "bottom": .402})
        self.assertTrue(guide.repeating_click_cycle([a, a], shifted))

    def test_distinct_actions_at_same_position_are_not_a_loop(self):
        self.controller.goal = "Save Workspace, Create, apoi Open"
        self.controller.screen_signature = "unchanged-page"
        self.controller.attempts = [
            dict(DECISION, instruction="Apasă Save Workspace", expected_result="Formular deschis",
                 screen_signature="unchanged-page"),
            dict(DECISION, instruction="Apasă Create", expected_result="Workspace creat",
                 screen_signature="unchanged-page"),
        ]
        next_step = guide.Decision.parse(json.dumps(dict(
            DECISION, instruction="Apasă Open", expected_result="Workspace deschis")))
        self.controller.accept_decision(self.controller.generation, next_step)
        self.assertEqual(self.controller.state, "waiting")
        self.assertEqual(self.controller.current, next_step)

    def test_same_action_on_a_new_page_is_allowed_but_unchanged_page_is_paused(self):
        record = dict(DECISION, screen_signature="page-one")
        self.assertFalse(guide.repeating_click_cycle(
            [record, record], dict(record, screen_signature="page-two")))
        self.assertTrue(guide.repeating_click_cycle([record, record], record))

    def test_page_signature_is_stable_across_formats_and_detects_change(self):
        image = QImage(53, 96, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFF)
        signature = guide.screen_signature(image)
        self.assertEqual(signature, guide.screen_signature(image.copy()))
        self.assertEqual(signature, guide.screen_signature(image.convertToFormat(QImage.Format.Format_RGB888)))
        image.fill(0x000000)
        self.assertNotEqual(signature, guide.screen_signature(image))

    def test_navigation_during_analysis_rejects_old_result_and_recaptures_after_pause(self):
        controller = self.controller
        controller.goal = "Creează workspace"
        controller.state = "thinking"
        controller.capture_started_at = time.monotonic() - .1
        controller.last_capture_at = time.monotonic()
        controller.history = [{"instruction": "Apasă Save Workspace", "verification": "succeeded"}]
        controller.pending = dict(DECISION, step=2)
        worker = Mock()
        controller.requests.add(worker)
        token = controller.generation
        history, pending = controller.history.copy(), controller.pending.copy()
        # Includes clicks during acquisition, before last_capture_at is set.
        controller.on_click(100, 100, controller.last_capture_at - .05)
        worker.requestInterruption.assert_called_once()
        self.assertEqual(controller.state, "settling")
        self.assertEqual(controller.goal, "Creează workspace")
        self.assertEqual(controller.history, history)
        self.assertEqual(controller.pending, pending)
        self.assertFalse(controller.caption.isVisible())
        with patch.object(controller.output, "say") as say:
            controller.accept_decision(token, guide.Decision.parse(json.dumps(DECISION)))
            controller.request_error(token, "ai.api_request")
        say.assert_not_called()
        self.assertIsNone(controller.current)
        self.assertEqual(controller.state, "settling")
        with patch.object(controller, "begin_capture") as capture:
            QTest.qWait(2600)
        capture.assert_called_once_with("decision")

    def test_navigation_during_capture_discards_scheduled_snapshot(self):
        controller = self.controller
        controller.goal = "Deschide meniul"
        controller.state = "capturing"
        controller.capture_started_at = time.monotonic()
        controller.capture_context = (controller.generation, controller.screen.geometry(), "decision")
        controller.capture_timer.start()
        controller.on_click(100, 100, time.monotonic())
        self.assertIsNone(controller.capture_context)
        self.assertFalse(controller.capture_timer.isActive())
        with patch.object(controller, "dispatch_ai") as dispatch:
            controller.capture_ready()
        dispatch.assert_not_called()
        self.assertEqual(controller.state, "settling")

    def test_old_queued_click_does_not_invalidate_current_capture(self):
        controller = self.controller
        controller.goal = "Deschide meniul"
        controller.state = "thinking"
        controller.capture_started_at = time.monotonic()
        token = controller.generation
        controller.on_click(100, 100, controller.capture_started_at - 1)
        self.assertEqual(controller.generation, token)
        self.assertEqual(controller.state, "thinking")
        self.assertFalse(controller.settle_timer.isActive())

    def test_click_outside_target_or_monitor_refreshes_without_verifying_step(self):
        for position in ((100, 100), (2500, 100)):
            with self.subTest(position=position):
                self.controller.cancel_session()
                self.controller.goal = "Deschide meniul"
                self.controller.accept_decision(self.controller.generation,
                                                guide.Decision.parse(json.dumps(DECISION)))
                self.controller.on_click(*position, time.monotonic())
                self.assertEqual(self.controller.state, "settling")
                self.assertIsNone(self.controller.pending)
                self.assertIsNone(self.controller.current)

    def test_microphone_error_has_voice_retry_and_refresh_restarts_voice(self):
        for reason in ("voice.microphone_open", "voice.audio_import", "voice.recording",
                       "voice.transcription", "no_speech"):
            with self.subTest(reason=reason):
                self.controller.cancel_session()
                with patch.object(self.controller.output, "say") as say:
                    self.controller.request_error(self.controller.generation, reason)
                message = say.call_args.args[0]
                self.assertIn("Control Spațiu", message)
                self.assertNotIn("Control Alt Spațiu", message)
                self.assertNotIn("verifica ecranul", message)
                with patch.object(self.controller, "start_voice") as voice, \
                        patch.object(self.controller, "begin_capture") as capture:
                    self.controller.refresh()
                voice.assert_called_once()
                capture.assert_not_called()

    def test_error_with_existing_goal_refreshes_capture_instead_of_voice(self):
        self.controller.goal = "Deschide meniul"
        with patch.object(self.controller.output, "say") as say:
            self.controller.request_error(self.controller.generation, "ai.api_request")
        self.assertIn("Control Alt Spațiu", say.call_args.args[0])
        with patch.object(self.controller, "start_voice") as voice, \
                patch.object(self.controller, "begin_capture") as capture:
            self.controller.refresh()
        voice.assert_not_called()
        capture.assert_called_once_with("decision")

    def test_mute_and_stale_audio_do_not_start_playback(self):
        output = SpeechOutput(enabled=False)
        output.say("Apasă Save.")
        self.assertFalse(output.requests)
        output.play(output.token - 1, b"obsolete audio")
        self.assertIsNone(output.player)

    def test_speech_cancel_interrupts_pending_network_without_audio(self):
        import asyncio
        import edge_tts
        class WaitingSpeech:
            async def stream(self):
                await asyncio.sleep(30)
                yield {"type": "audio", "data": b"obsolete audio"}
        request = SpeechOutputRequest(1, "Apasă Save.", "ro-RO-AlinaNeural")
        delivered = []
        request.ready.connect(lambda *args: delivered.append(args))
        with patch.object(edge_tts, "Communicate", return_value=WaitingSpeech()):
            request.start()
            deadline = time.monotonic() + 2
            while request.task is None and time.monotonic() < deadline:
                QTest.qWait(10)
            request.cancel()
            self.assertTrue(request.wait(1500))
        self.app.processEvents()
        self.assertFalse(delivered)


if __name__ == "__main__":
    unittest.main()
