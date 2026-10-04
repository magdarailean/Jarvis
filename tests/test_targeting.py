import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from jarvis.features.targeting.grounding import ground_response, normalized_bounds, locate


class TargetingTests(unittest.TestCase):
    def setUp(self):
        self.decision = dict(status="action", action="click", instruction="Apasă Create.",
                             expected_result="Editor deschis", previous_result="succeeded",
                             target=dict(left=.1, top=.1, right=.2, bottom=.2))
        self.context = {"screenshot": {"width": 1920, "height": 1080}}

    def apply(self, locator, **kwargs):
        return json.loads(ground_response(json.dumps(self.decision), b"synthetic", self.context,
                                          "fake-key", "test-model", "image/jpeg",
                                          locator=locator, **kwargs))

    def test_replaces_wrong_planner_box_preserves_history(self):
        locator = Mock(return_value=json.dumps(dict(found=True, box_2d=[250, 500, 300, 600])))
        result = self.apply(locator)
        self.assertEqual(result["target"], dict(left=.5, top=.25, right=.6, bottom=.3))
        self.assertEqual(result["previous_result"], "succeeded")
        self.assertEqual(result["instruction"], self.decision["instruction"])
        locator.assert_called_once_with("fake-key", b"synthetic", "Apasă Create.",
                                        1920, 1080, "test-model", "image/jpeg")

    def test_absent_or_failed_location_never_uses_planner_box(self):
        for locator in (Mock(return_value='{"found":false,"box_2d":null}'),
                        Mock(side_effect=TimeoutError), Mock(return_value="not json")):
            with self.subTest(locator=locator):
                result = self.apply(locator)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["action"], "none")
                self.assertIsNone(result["target"])
                self.assertEqual(result["previous_result"], "succeeded")

    def test_no_extra_call_for_completed_blocked_or_cancelled(self):
        locator = Mock()
        self.apply(locator, cancelled=lambda: True)
        for status in ("complete", "blocked"):
            self.decision.update(status=status, action="none", target=None)
            self.assertEqual(self.apply(locator), self.decision)
        locator.assert_not_called()

    def test_failures_are_distinguished_without_leaking_server_content(self):
        for error, reason, status in (
            (HTTPError("private-url", 401, "secret-key", {}, None), "http_error", 401),
            (URLError("secret-key"), "network_error", None),
            (ValueError("secret-key"), "invalid_response", None),
        ):
            report = Mock()
            result = self.apply(Mock(side_effect=error), report=report)
            report.assert_called_once_with(reason=reason, http_status=status)
            self.assertNotIn("secret-key", str(result))
            self.assertEqual(result["status"], "blocked")

    def test_not_found_has_a_separate_diagnostic(self):
        report = Mock()
        self.apply(Mock(return_value='{"found":false,"box_2d":null}'), report=report)
        report.assert_called_once_with(reason="not_found", http_status=None)

    def test_rejects_nonfinite_bool_reversed_and_outside_bounds(self):
        for bounds in (
            [0, -1, 10, 10], [0, 0, 10, 1001], [0, 10, 10, 10],
            [20, 0, 10, 10], [0, True, 10, 10], [0, 0, 10, float("nan")],
            [.25, .5, .3, .6], [1, 2, 3], {"left": 0, "top": 0, "right": 10, "bottom": 10},
        ):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                normalized_bounds(json.dumps(dict(found=True, box_2d=bounds)), 1920, 1080)

    def test_resolution_independent_mapping(self):
        for width, height in ((1280, 720), (1920, 1080), (1080, 1920)):
            result = normalized_bounds(json.dumps(dict(found=True, box_2d=[200, 250, 400, 500])), width, height)
            self.assertEqual(result, dict(left=.25, top=.2, right=.5, bottom=.4))

    def test_gemini_scale_is_not_mistaken_for_pixels(self):
        result = normalized_bounds('{"found":true,"box_2d":[100,800,200,950]}', 1920, 1080)
        # Right-hand control stays on the right; dividing 800 by 1920 was wrong.
        self.assertEqual(result, dict(left=.8, top=.1, right=.95, bottom=.2))

    def test_full_image_bounds(self):
        result = normalized_bounds('{"found":true,"box_2d":[0,0,1000,1000]}', 720, 1280)
        self.assertEqual(result, dict(left=0, top=0, right=1, bottom=1))

    @patch("jarvis.features.targeting.grounding.urlopen")
    def test_transport_sends_exact_image_size_and_no_planner_coordinates(self, urlopen):
        response = '{"found":false,"box_2d":null}'
        body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": response}}]})
        urlopen.return_value.__enter__.return_value.read.return_value = body
        self.assertEqual(locate("fake", b"test", "Create", 1920, 1080, "model", "image/jpeg"), response)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        context = json.loads(payload["messages"][1]["content"][0]["text"])
        self.assertEqual(context, dict(instruction="Create", image_width=1920, image_height=1080))
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]["required"], ["found", "box_2d"])


if __name__ == "__main__":
    unittest.main()
