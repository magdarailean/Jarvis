"""Offline tests: no microphone, real screenshots, model downloads or API calls."""
import json
import io
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import workingVersion2 as guide
import diagnostics_v2 as diagnostics
from voice_input_v2 import SpeechGate, VoiceRequest


def action(**changes):
    data = {"status": "action", "action": "click", "instruction": "Click Settings",
            "expected_result": "Settings opens", "previous_result": "none",
            "target": {"left": .3, "top": .3, "right": .4, "bottom": .4}}
    data.update(changes)
    return guide.Decision.parse(json.dumps(data))


class DecisionTests(unittest.TestCase):
    def test_malformed_ai_targets_are_rejected(self):
        for target in (None, {}, {"left": True, "top": .1, "right": .4, "bottom": .5},
                       {"left": .5, "top": .1, "right": .4, "bottom": .5},
                       {"left": -.1, "top": .1, "right": .4, "bottom": .5},
                       {"left": float("nan"), "top": .1, "right": .4, "bottom": .5}):
            with self.subTest(target=target), self.assertRaises(ValueError):
                action(target=target)

    def test_click_mapping_handles_negative_origins_and_scaling(self):
        self.assertEqual(guide.normalized_click(-960, 600, (-1920, 0, 0, 1200)), (.5, .5))
        self.assertIsNone(guide.normalized_click(20, 600, (-1920, 0, 0, 1200)))
        self.assertTrue(guide.Target(.4, .4, .6, .6).contains(.5, .5))

    def test_endpoint_detector_waits_for_speech_then_silence(self):
        gate = SpeechGate()
        for _ in range(20):
            self.assertFalse(gate.observe(0))
        for _ in range(10):
            self.assertFalse(gate.observe(.1))
        self.assertTrue(gate.has_speech)
        stopped = False
        for _ in range(30):
            if gate.observe(0):
                stopped = True
                break
        self.assertTrue(stopped)

    def test_no_speech_times_out_without_false_transcript(self):
        gate = SpeechGate(start_timeout=.5)
        for _ in range(12):
            stopped = gate.observe(0)
        self.assertTrue(stopped)
        self.assertFalse(gate.has_speech)


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        diagnostics.configure(debug=True, stream=self.output)

    def tearDown(self):
        with patch.object(diagnostics.sys, "stdout", None):
            diagnostics.configure()

    def test_vendor_error_is_useful_but_redacts_credentials_and_transcript(self):
        diagnostics.protect("private-test-key")
        diagnostics.protect("private-spoken-request")
        error = RuntimeError("Invalid key private-test-key; private-spoken-request")
        error.status_code = 403
        diagnostics.exception("ai.request.error", error, stage="api_request", session=2)
        output = self.output.getvalue()
        self.assertIn('"http_status": 403', output)
        self.assertIn('"stage": "api_request"', output)
        self.assertIn("Invalid key", output)
        self.assertNotIn("private-test-key", output)
        self.assertNotIn("private-spoken-request", output)

    def test_reflected_request_body_is_never_dumped(self):
        error = RuntimeError('Server echoed original_goal=secret request; base64=iVBORfake')
        diagnostics.exception("ai.request.error", error)
        output = self.output.getvalue()
        self.assertIn("request data; omitted", output)
        self.assertNotIn("secret request", output)
        self.assertNotIn("iVBORfake", output)

    def test_debug_stack_does_not_include_locals(self):
        private_local = "do-not-log-this-local"
        try:
            raise ValueError("Invalid target")
        except ValueError as error:
            diagnostics.exception("validation.error", error)
        self.assertIn('"stack"', self.output.getvalue())
        self.assertNotIn(private_local, self.output.getvalue())


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.controller = guide.GuideController(demo=True, start_observer=False)
        self.controller.goal = "Open settings"
        self.controller.screen = self.app.primaryScreen()
        self.controller.physical_bounds = (0, 0, 1600, 1600)
        self.controller.state = "thinking"

    def tearDown(self):
        self.controller.cancel_session()
        self.wait_until(lambda: not self.controller.requests and not self.controller.voice_requests)
        self.controller.shutdown()
        self.app.processEvents()

    def wait_until(self, predicate, timeout=6):
        end = time.monotonic() + timeout
        while not predicate() and time.monotonic() < end:
            QTest.qWait(20)
        self.assertTrue(predicate(), f"Timed out; state={self.controller.state}")

    def test_only_pointer_is_visible_no_panel_or_transcript(self):
        c = self.controller
        self.app.processEvents()
        self.assertEqual([w for w in QApplication.topLevelWidgets() if w.isVisible()], [c.pointer])
        self.assertFalse(hasattr(c, "input"))
        self.assertFalse(hasattr(c, "log"))
        for mode in ("listening", "processing", "success", "error", "idle"):
            c.pointer.set_mode(mode)
            self.assertFalse(c.pointer.grab().isNull())
        flags = c.pointer.windowFlags()
        self.assertTrue(flags & guide.Qt.WindowType.WindowTransparentForInput)
        self.assertTrue(flags & guide.Qt.WindowType.WindowDoesNotAcceptFocus)

    def test_wrong_click_and_old_click_do_not_advance(self):
        c = self.controller
        c.accept_decision(c.generation, action())
        c.on_click(100, 100, time.monotonic())
        self.assertEqual(c.state, "waiting")
        c.on_click(560, 560, c.armed_at - 1)
        self.assertEqual(c.state, "waiting")
        c.on_click(560, 560, time.monotonic())
        self.assertEqual(c.state, "settling")
        self.assertEqual(c.pointer.mode, "processing")
        pending = c.pending
        c.on_click(560, 560, time.monotonic())
        self.assertIs(c.pending, pending)
        self.assertEqual(len(c.history), 0)

    def attempt(self):
        self.controller.on_click(560, 560, time.monotonic())
        self.controller.settle_timer.stop()

    def test_successful_verification_counts_step_but_failed_does_not(self):
        c = self.controller
        c.accept_decision(c.generation, action())
        self.attempt()
        c.accept_decision(c.generation, action(previous_result="failed"))
        self.assertEqual(len(c.history), 0)
        self.assertEqual(c.state, "waiting")
        self.attempt()
        c.accept_decision(c.generation, action(previous_result="succeeded"))
        self.assertEqual(len(c.history), 1)

    def test_completion_requires_verification_and_erases_transcript(self):
        c = self.controller
        c.accept_decision(c.generation, action())
        self.attempt()
        c.accept_decision(c.generation, action(status="complete", action="none", target=None,
                                             previous_result="uncertain"))
        self.assertEqual(c.state, "error")
        self.assertIsNotNone(c.pending)
        c.accept_decision(c.generation, action(status="complete", action="none", target=None,
                                             previous_result="succeeded"))
        self.assertEqual(c.state, "idle")
        self.assertEqual(c.goal, "")
        self.assertEqual(c.history, [])
        self.assertEqual(c.pointer.mode, "success")

    def test_non_click_instructions_are_blocked_without_text_ui(self):
        c = self.controller
        c.accept_decision(c.generation, action(action="type"))
        self.assertEqual(c.state, "blocked")
        self.assertEqual(c.pointer.mode, "error")

    def test_cancel_discards_late_results_and_capture(self):
        c = self.controller
        token = c.generation
        c.accept_decision(token, action())
        self.attempt()
        c.cancel_session()
        c.accept_decision(token, action())
        c.voice_recognized(token, "late transcript")
        c.request_error(token, "late error")
        self.assertEqual(c.state, "idle")
        self.assertEqual(c.goal, "")
        self.assertIsNone(c.current)
        self.assertFalse(c.settle_timer.isActive())
        self.assertTrue(c.pointer.follow_cursor)

    def test_refresh_does_not_verify_unattempted_step(self):
        c = self.controller
        c.accept_decision(c.generation, action())
        c.accept_decision(c.generation, action(instruction="Updated target"))
        self.assertEqual(len(c.history), 0)
        self.assertEqual(c.current.instruction, "Updated target")

    def test_hotkey_finishes_recording_and_ignores_busy_state(self):
        c = self.controller
        request = Mock()
        c.voice_request = request
        c.state = "listening"
        c.activate()
        request.finish.assert_called_once()
        c.state = "thinking"
        token = c.generation
        c.activate()
        self.assertEqual(c.generation, token)
        c.voice_request = None

    def test_full_voice_demo_with_fresh_captures_and_responsive_gui(self):
        c = self.controller
        c.cancel_session()
        captures = []

        def fake_capture(_screen, *_):
            captures.append(c.state)
            self.assertFalse(c.pointer.isVisible())
            pixmap = QPixmap(800, 800)
            pixmap.fill()
            return pixmap

        ticks = []
        heartbeat = QTimer()
        heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
        heartbeat.start(30)
        with patch.object(guide, "physical_monitor_bounds", return_value=(0, 0, 1600, 1600)), \
             patch.object(type(c.screen), "grabWindow", fake_capture):
            c.activate()
            self.wait_until(lambda: c.state == "listening")
            self.assertEqual(c.pointer.mode, "listening")
            c.activate()  # Second Ctrl+Space ends the simulated listening.
            self.wait_until(lambda: c.state == "thinking")
            self.assertEqual(c.pointer.mode, "processing")
            self.wait_until(lambda: c.state == "waiting")
            self.assertGreater(len(ticks), 20)
            self.assertEqual(c.pointer.mode, "pointing")
            c.on_click(640, 688, time.monotonic())
            self.wait_until(lambda: c.state == "thinking")
            self.wait_until(lambda: c.state == "waiting")
            self.assertEqual(len(c.history), 1)
            c.on_click(960, 688, time.monotonic())
            self.wait_until(lambda: c.state == "idle")
            self.assertEqual(c.pointer.mode, "success")
            self.assertEqual(c.goal, "")
            self.assertEqual(len(captures), 3)
            self.assertGreater(len(ticks), 100)
        heartbeat.stop()

    def test_voice_worker_uses_silence_to_finish_without_real_microphone(self):
        import numpy as np
        import sounddevice as sd
        chunks = iter([np.full(800, .1, dtype=np.float32).tobytes()] * 10
                      + [np.zeros(800, dtype=np.float32).tobytes()] * 30)
        stream = Mock()
        stream.read.side_effect = lambda _: (next(chunks), False)
        engine = Mock()
        engine.transcribe.return_value = "Deschide setările"
        request = VoiceRequest(2, engine)
        results, errors = [], []
        request.recognized.connect(lambda token, text: results.append((token, text)))
        request.error.connect(lambda token, error: errors.append(error))
        with patch.object(sd, "RawInputStream") as stream_class:
            stream_class.return_value.__enter__.return_value = stream
            request.start()
            self.wait_until(lambda: not request.isRunning())
            self.app.processEvents()
        self.assertEqual(errors, [])
        self.assertEqual(results, [(2, "Deschide setările")])
        engine.transcribe.assert_called_once()

    def test_worker_encodes_image_and_calls_sdk_without_network(self):
        from google import genai
        response = SimpleNamespace(output_text=json.dumps({
            "status": "complete", "action": "none", "instruction": "Done",
            "expected_result": "", "previous_result": "none", "target": None}))
        image = QImage(32, 32, QImage.Format.Format_RGB32)
        image.fill(0)
        request = guide.AIRequest(3, image, {"goal": "test"}, False, "gemini-3.8-flash")
        results, errors = [], []
        request.result.connect(lambda token, decision: results.append((token, decision)))
        request.error.connect(lambda token, error: errors.append(error))
        with patch.object(guide, "load_api_key", return_value="offline-placeholder"), \
             patch.object(genai, "Client") as client:
            client.return_value.__enter__.return_value.interactions.create.return_value = response
            request.start()
            self.wait_until(lambda: not request.isRunning())
            self.app.processEvents()
            arguments = client.return_value.__enter__.return_value.interactions.create.call_args.kwargs
            self.assertTrue(arguments["input"][1]["data"].startswith("iVBOR"))
            self.assertEqual(arguments["timeout"], 45.0)
        self.assertEqual(errors, [])
        self.assertEqual(results[0][0], 3)

    def test_cancel_while_voice_runs_discards_actual_late_response(self):
        c = self.controller
        request = VoiceRequest(c.generation, c.engine, demo=True, parent=c)
        c.voice_requests.add(request)
        c.voice_request = request
        request.recognized.connect(c.voice_recognized)
        request.finished.connect(c.worker_finished)
        request.start()
        c.cancel_session()
        self.wait_until(lambda: not c.voice_requests)
        self.assertEqual(c.state, "idle")
        self.assertEqual(c.goal, "")

    def test_invalid_monitor_mapping_prevents_capture(self):
        c = self.controller
        c.state = "waiting"
        with patch.object(guide, "physical_monitor_bounds", side_effect=ValueError):
            c.request_decision()
        self.assertEqual(c.state, "error")
        self.assertFalse(c.capture_timer.isActive())

    def test_file_menu_click_is_verified_before_pointing_to_new_file(self):
        c = self.controller
        file_menu = action(instruction="Click File", expected_result="File menu opens")
        new_file = action(instruction="Click New Text File", previous_result="succeeded",
                          target={"left": .05, "top": .1, "right": .2, "bottom": .15})
        with self.assertLogs(diagnostics.LOGGER, level="INFO") as logs:
            c.accept_decision(c.generation, file_menu)
            self.attempt()
            c.accept_decision(c.generation, new_file)
        self.assertEqual(c.state, "waiting")
        self.assertEqual(c.current.instruction, "Click New Text File")
        self.assertEqual(len(c.history), 1)
        self.assertIn("click.accepted", "\n".join(logs.output))
        self.assertIn("step.verification", "\n".join(logs.output))
        self.assertIn("Click New Text File", "\n".join(logs.output))

    def test_ai_blocked_reason_is_logged_separately_from_api_error(self):
        c = self.controller
        with self.assertLogs(diagnostics.LOGGER, level="INFO") as logs:
            c.accept_decision(c.generation, action(status="blocked", action="none", target=None,
                                                  instruction="The File menu is not visible."))
        output = "\n".join(logs.output)
        self.assertIn("ai.blocked", output)
        self.assertIn("The File menu is not visible", output)
        self.assertNotIn("session.error", output)
        self.assertEqual(c.state, "blocked")

    def test_malformed_ai_response_reports_validation_stage(self):
        from google import genai
        image = QImage(32, 32, QImage.Format.Format_RGB32)
        image.fill(0)
        request = guide.AIRequest(3, image, {"original_goal": "private-spoken-request"},
                                  False, "gemini-3.8-flash")
        errors = []
        request.error.connect(lambda token, error: errors.append(error))
        with patch.object(guide, "load_api_key", return_value="private-test-key"), \
             patch.object(genai, "Client") as client, \
             self.assertLogs(diagnostics.LOGGER, level="INFO") as logs:
            client.return_value.__enter__.return_value.interactions.create.return_value = SimpleNamespace(
                output_text='{"status":"action"}')
            request.start()
            self.wait_until(lambda: not request.isRunning())
            self.app.processEvents()
        self.assertEqual(errors, ["ai.response_validation"])
        output = "\n".join(logs.output)
        self.assertIn("Missing or invalid action", output)
        self.assertIn("response_validation", output)
        self.assertNotIn("private-spoken-request", output)
        self.assertNotIn("private-test-key", output)

    def test_microphone_failure_reports_device_error(self):
        import sounddevice as sd
        request = VoiceRequest(3, Mock())
        errors = []
        request.error.connect(lambda token, error: errors.append(error))
        with patch.object(sd, "RawInputStream", side_effect=RuntimeError("No default input device")), \
             self.assertLogs(diagnostics.LOGGER, level="INFO") as logs:
            request.start()
            self.wait_until(lambda: not request.isRunning())
            self.app.processEvents()
        self.assertEqual(errors, ["voice.microphone_open"])
        self.assertIn("No default input device", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
