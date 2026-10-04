"""Offline protocol/GUI checks; do not consume Codex allowance or record audio."""
import json
import os
import queue
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import codex_bridge_v3 as bridge
import workingVersion3_Codex as guide


DECISION = {
    "status": "action", "action": "click", "instruction": "Click the button",
    "expected_result": "Menu opens", "previous_result": "none",
    "target": {"left": .3, "top": .3, "right": .4, "bottom": .4},
}


class FakeStream:
    def __init__(self):
        self.lines = queue.Queue()

    def __iter__(self):
        return self

    def __next__(self):
        line = self.lines.get(timeout=3)
        if line is None:
            raise StopIteration
        return line

    def feed(self, value):
        self.lines.put(json.dumps(value) + "\n")

    def close(self):
        self.lines.put(None)


class FakeInput:
    def __init__(self, process):
        self.process = process

    def write(self, line):
        self.process.receive(json.loads(line))

    def flush(self):
        pass

    def close(self):
        pass


class FakeProcess:
    def __init__(self, auth="chatgpt", status="completed", complete=True, tool_request=False):
        self.stdout, self.stderr = FakeStream(), FakeStream()
        self.stdin = FakeInput(self)
        self.auth, self.status, self.complete, self.tool_request = auth, status, complete, tool_request
        self.sent = []
        self.stopped = False

    def receive(self, request):
        self.sent.append(request)
        method, identifier = request.get("method"), request.get("id")
        if method == "initialize":
            self.stdout.feed({"id": identifier, "result": {}})
        elif method == "account/read":
            self.stdout.feed({"id": identifier, "result": {
                "account": {"type": self.auth, "email": "not-logged@example.com"}}})
        elif method == "thread/start":
            self.stdout.feed({"method": "thread/started", "params": {"thread": {"id": "thread1"}}})
            self.stdout.feed({"id": identifier, "result": {"thread": {"id": "thread1", "ephemeral": True},
                                                              "model": "test-model"}})
        elif method == "turn/start":
            if self.tool_request:
                self.stdout.feed({"id": 99, "method": "item/tool/call", "params": {}})
            # Events deliberately arrive before the turn/start RPC acknowledgement.
            self.stdout.feed({"method": "item/completed", "params": {
                "threadId": "thread1", "turnId": "turn1",
                "item": {"type": "agentMessage", "phase": "commentary", "text": "Not the final JSON"}}})
            self.stdout.feed({"method": "item/completed", "params": {
                "threadId": "thread1", "turnId": "turn1",
                "item": {"type": "agentMessage", "phase": "final_answer", "text": json.dumps(DECISION)}}})
            if self.complete:
                self.stdout.feed({"method": "turn/completed", "params": {
                    "threadId": "thread1", "turn": {"id": "turn1", "status": self.status,
                        "items": [], "error": {"message": "Unavailable model"} if self.status != "completed" else None}}})
            self.stdout.feed({"id": identifier, "result": {"turn": {"id": "turn1"}}})

    def poll(self):
        return 0 if self.stopped else None

    def terminate(self):
        self.stopped = True
        self.stdout.close()
        self.stderr.close()

    kill = terminate

    def wait(self, timeout=None):
        return 0


class ProtocolTests(unittest.TestCase):
    def analyze(self, process, timeout=2, cancelled=None):
        client = bridge.CodexSession(cancelled, timeout, process_factory=lambda *a, **k: process)
        with patch.object(bridge, "find_codex", return_value="codex.exe"):
            return client.analyze("Synthetic test prompt", "data:image/png;base64,FAKE", guide.SCHEMA)

    def test_authenticated_image_request_strict_schema_and_ephemeral_readonly_thread(self):
        process = FakeProcess()
        result = self.analyze(process)
        self.assertEqual(json.loads(result), DECISION)
        self.assertTrue(process.stopped)
        start = next(r for r in process.sent if r.get("method") == "thread/start")["params"]
        turn = next(r for r in process.sent if r.get("method") == "turn/start")["params"]
        self.assertTrue(start["ephemeral"])
        self.assertEqual(start["sandbox"], "read-only")
        self.assertEqual(start["environments"], [])
        self.assertEqual(turn["input"][1]["type"], "image")
        self.assertFalse(turn["outputSchema"]["additionalProperties"])
        self.assertFalse(turn["outputSchema"]["properties"]["target"]["anyOf"][1]["additionalProperties"])
        self.assertNotIn("additionalProperties", guide.SCHEMA)  # Original schema unchanged.

    def test_api_key_auth_is_rejected_without_inference(self):
        process = FakeProcess(auth="apiKey")
        with self.assertRaisesRegex(bridge.CodexProtocolError, "ChatGPT login required"):
            self.analyze(process)
        self.assertFalse(any(r.get("method") == "turn/start" for r in process.sent))
        self.assertTrue(process.stopped)

    def test_failed_turn_is_not_accepted_as_success(self):
        process = FakeProcess(status="failed")
        with self.assertRaisesRegex(bridge.CodexProtocolError, "Unavailable model"):
            self.analyze(process)
        self.assertTrue(process.stopped)

    def test_tools_are_rejected_instead_of_executed(self):
        process = FakeProcess(tool_request=True)
        self.analyze(process)
        denial = next(r for r in process.sent if r.get("id") == 99)
        self.assertEqual(denial["error"]["code"], -32601)

    def test_deadline_closes_unresponsive_runtime(self):
        process = FakeProcess(complete=False)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.analyze(process, timeout=.2)
        self.assertTrue(process.stopped)
        self.assertLess(time.monotonic() - started, 2)

    def test_cancel_before_start_does_not_launch_process(self):
        cancelled = threading.Event()
        cancelled.set()
        process = FakeProcess()
        with self.assertRaises(bridge.CodexCancelled):
            self.analyze(process, cancelled=cancelled)
        self.assertEqual(process.sent, [])


class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def wait_until(self, predicate, timeout=6):
        end = time.monotonic() + timeout
        while not predicate() and time.monotonic() < end:
            QTest.qWait(20)
        self.assertTrue(predicate())

    def test_full_demo_voice_click_verification_and_fresh_initial_screen(self):
        controller = guide.GuideController(demo=True, start_observer=False)
        captures, ticks = [], []
        heartbeat = QTimer()
        heartbeat.timeout.connect(lambda: ticks.append(True))
        heartbeat.start(30)

        def capture(screen, *_):
            self.assertFalse(controller.pointer.isVisible())
            captures.append(True)
            image = QPixmap(800, 800)
            image.fill()
            return image

        try:
            with patch.object(guide, "physical_monitor_bounds", return_value=(0, 0, 1600, 1600)), \
                 patch.object(type(self.app.primaryScreen()), "grabWindow", capture):
                controller.activate()
                self.wait_until(lambda: controller.state == "listening")
                controller.activate()
                self.wait_until(lambda: controller.state == "waiting")
                self.assertEqual(len(captures), 2)  # Before voice, then after transcription.
                self.assertEqual([w for w in QApplication.topLevelWidgets() if w.isVisible()], [controller.pointer])
                controller.on_click(640, 688, time.monotonic())
                self.wait_until(lambda: controller.state == "waiting")
                self.assertEqual(len(controller.history), 1)
                controller.on_click(960, 688, time.monotonic())
                self.wait_until(lambda: controller.state == "idle")
                self.assertEqual(controller.pointer.mode, "success")
                self.assertEqual(controller.goal, "")
                self.assertEqual(len(captures), 4)
                self.assertGreater(len(ticks), 100)
        finally:
            heartbeat.stop()
            controller.cancel_session()
            self.wait_until(lambda: not controller.requests and not controller.voice_requests)
            controller.shutdown()

    def test_cancel_stops_worker_and_ignores_late_results(self):
        controller = guide.GuideController(demo=True, start_observer=False)
        image = QImage(32, 32, QImage.Format.Format_RGB32)
        request = guide.AIRequest(controller.generation, image,
                                  {"verified_steps": [], "pending_attempt": None}, True, "", controller)
        controller.requests.add(request)
        request.result.connect(controller.accept_decision)
        request.finished.connect(controller.worker_finished)
        request.start()
        controller.cancel_session()
        self.wait_until(lambda: not controller.requests)
        self.assertTrue(request.cancelled.is_set())
        self.assertEqual(controller.state, "idle")
        controller.shutdown()

    def test_real_worker_uses_codex_bridge_not_gemini(self):
        image = QImage(32, 32, QImage.Format.Format_RGB32)
        image.fill(0)
        request = guide.AIRequest(2, image, {"original_goal": "private goal"}, False, "test-model")
        results, errors = [], []
        request.result.connect(lambda token, decision: results.append(decision))
        request.error.connect(lambda token, error: errors.append(error))
        with patch.object(guide, "CodexSession") as session:
            session.return_value.analyze.return_value = json.dumps(DECISION)
            request.start()
            self.wait_until(lambda: not request.isRunning())
            self.app.processEvents()
            args = session.return_value.analyze.call_args.args
            self.assertTrue(args[1].startswith("data:image/png;base64,iVBOR"))
            self.assertEqual(args[3], "test-model")
        self.assertEqual(errors, [])
        self.assertEqual(results[0].action, "click")


if __name__ == "__main__":
    unittest.main()
