import base64
from copy import deepcopy
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from jarvis.app import create_application
from jarvis.features.ai.openrouter import OpenRouterProvider, build_payload
from jarvis.features.ai.pointer_location import location_payload, pointer_index
from jarvis.features.targeting.grounding import build_location_payload
from jarvis.features.interaction.intent import VisualIntent


def completion(content):
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}).encode()


class Reply(QObject):
    readyRead = Signal()
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.raw, self.status, self.aborted = b"", 200, False

    def bytesAvailable(self):
        return len(self.raw)

    def attribute(self, _):
        return self.status

    def readAll(self):
        return self.raw

    def error(self):
        return SimpleNamespace(name="TestError")

    def abort(self):
        self.aborted = True

    def deliver(self, content, status=200):
        self.raw, self.status = completion(content), status
        self.finished.emit()


class Network:
    def __init__(self):
        self.calls = []

    def post(self, request, data):
        reply = Reply()
        self.calls.append((json.loads(data), reply))
        return reply


class MainPointerLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()
        image = QImage(3840, 2160, QImage.Format.Format_RGB32)
        image.fill(0xffffffff)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        cls.frame = SimpleNamespace(png=bytes(data))

    def setUp(self):
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake-test", "OPENROUTER_MODEL": "model",
                                          "JARVIS_TARGET_MODEL": ""})
        self.env.start()
        self.provider = OpenRouterProvider()
        self.provider.network = Network()
        self.request = SimpleNamespace(id="request", question="Arată-mi Google", history=(),
            visual_intent=VisualIntent.GUIDE, guide_context={"original_goal": "Google"}, frame=self.frame)
        self.payload = dict(text="Apasă Google.", guide_status="next", completion_evidence="", actions=[
            dict(type="pointer/cursor", id="next", text="Apasă Google.", target=[.1,.1,.2,.2],
                 target_text="Google", target_confidence=.98, placement="auto")])
        self.results, self.errors, self.diagnostics = [], [], []
        self.provider.succeeded.connect(lambda identifier, result: self.results.append((identifier, result)))
        self.provider.failed.connect(lambda *args: self.errors.append(args))
        self.provider.diagnostic.connect(lambda *args: self.diagnostics.append(args))

    def tearDown(self):
        self.provider.cancel()
        self.provider.deleteLater()
        self.env.stop()

    def plan(self):
        self.provider.send(self.request)
        self.provider.network.calls[-1][1].deliver(self.payload)

    def test_restores_previous_location_contract_and_preserves_every_other_field(self):
        original = deepcopy(self.payload)
        self.plan()
        self.assertEqual(self.results, [])
        self.assertEqual(len(self.provider.network.calls), 2)
        self.assertEqual(self.provider.network.calls[0][0], build_payload(self.request, (), "model"))
        wire = self.provider.network.calls[1][0]
        content = wire["messages"][1]["content"]
        image = base64.b64decode(content[1]["image_url"]["url"].split(",",1)[1])
        self.assertEqual((QImage.fromData(image).width(), QImage.fromData(image).height()), (1920,1080))
        self.assertEqual(wire, build_location_payload(image, "Apasă Google.", 1920,1080,"model","image/jpeg"))
        self.assertNotIn("target", json.loads(content[0]["text"]))
        self.provider.network.calls[-1][1].deliver(dict(found=True, box_2d=[100,800,200,900]))
        expected = deepcopy(original)
        expected["actions"][0]["target"] = [.8,.1,.9,.2]
        self.assertEqual(self.results, [("request", expected)])
        self.assertEqual(self.payload, original)
        self.assertIsNone(self.provider._context)
        self.assertIsNone(self.provider._location)

    def test_explain_and_guide_completion_do_not_trigger_location(self):
        for intent, payload in (
            (VisualIntent.EXPLAIN, dict(text="Explicație", actions=[dict(type="callout", id="one", text="Text", target=None)])),
            (VisualIntent.GUIDE, dict(text="Gata", actions=[], guide_status="complete", completion_evidence="Google visible")),
            (VisualIntent.GUIDE, dict(text="Așteaptă", actions=[], guide_status="wait", completion_evidence="")),
        ):
            with self.subTest(intent=intent, payload=payload):
                before = len(self.provider.network.calls)
                self.request.visual_intent = intent
                self.provider.send(self.request)
                self.provider.network.calls[-1][1].deliver(payload)
                self.assertEqual(len(self.provider.network.calls), before+1)
                self.assertEqual(self.results[-1][1], payload)

    def test_auto_preserves_non_pointer_actions_and_response(self):
        self.request.visual_intent = VisualIntent.AUTO
        self.payload["actions"].append(dict(type="highlight", id="keep", target=[.3,.3,.4,.4]))
        self.plan()
        self.provider.network.calls[-1][1].deliver(dict(found=True, box_2d=[100,800,200,900]))
        self.assertEqual(self.results[-1][1]["actions"][1], self.payload["actions"][1])

    def test_location_failures_preserve_text_and_remove_guessed_pointer(self):
        for content, status in ((dict(found=False, box_2d=None),200),
                                (dict(found=True,box_2d=[1,2,3,2000]),200), ({},401)):
            with self.subTest(content=content, status=status):
                self.plan()
                self.provider.network.calls[-1][1].deliver(content, status)
                result = self.results[-1][1]
                self.assertEqual(result["text"], self.payload["text"])
                self.assertEqual(result["guide_status"], "next")
                self.assertEqual(result["actions"], [])
                self.assertEqual(self.errors, [])

    def test_cancel_in_location_phase_discards_late_answer_and_releases_context(self):
        self.plan()
        reply = self.provider.network.calls[-1][1]
        self.provider.cancel()
        self.assertTrue(reply.aborted)
        self.assertIsNone(self.provider._location)
        reply.deliver(dict(found=True, box_2d=[100,800,200,900]))
        self.assertEqual(self.results, [])

    def test_new_request_rejects_old_location_reply(self):
        self.plan()
        old = self.provider.network.calls[-1][1]
        self.request.id = "new"
        self.provider.send(self.request)
        new = self.provider.reply
        old.deliver(dict(found=True, box_2d=[100,800,200,900]))
        self.assertEqual(self.results, [])
        self.assertIs(self.provider.reply, new)

    def test_missing_image_never_uses_planner_coordinates(self):
        self.request.frame = None
        self.plan()
        self.assertEqual(len(self.provider.network.calls), 1)
        self.assertEqual(self.results[-1][1]["actions"], [])

    def test_existing_eligibility_rules_are_preserved(self):
        self.payload["actions"][0]["target_confidence"] = .5
        self.assertIsNone(pointer_index(self.payload, self.request))
        self.plan()
        self.assertEqual(len(self.provider.network.calls), 1)

    def test_portrait_image_preserves_aspect_ratio(self):
        image = QImage(1080,1920,QImage.Format.Format_RGB32)
        image.fill(0xffffffff)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer,"PNG")
        buffer.close()
        _, width, height = location_payload(SimpleNamespace(png=bytes(data)), self.payload, 0, "model")
        self.assertEqual((width,height), (1080,1920))


if __name__ == "__main__":
    unittest.main()
