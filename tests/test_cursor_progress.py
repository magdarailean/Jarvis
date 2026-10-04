import json
import unittest

from jarvis.features.targeting.progress import evaluate, extend_schema


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.action = dict(status="action", action="click", instruction="Apasă Google.",
                           expected_result="Browser deschis", previous_result="none",
                           target=dict(left=.1, top=.1, right=.2, bottom=.2),
                           goal_state="in_progress", goal_evidence="Desktop visible",
                           control_name="Google Chrome", action_purpose="Deschide browserul",
                           page_context="Desktop")

    def evaluate(self, data=None, **context):
        response, waiting, _ = evaluate(json.dumps(data or self.action), context)
        return json.loads(response), waiting

    def test_achieved_goal_overrides_extra_action_and_says_done(self):
        data = dict(self.action, goal_state="achieved", goal_evidence="Browser window visible, not maximized")
        result, waiting = self.evaluate(data)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["action"], "none")
        self.assertIsNone(result["target"])
        self.assertTrue(result["instruction"].startswith("Gata"))
        self.assertFalse(waiting)

    def test_pending_action_must_be_verified_before_done(self):
        data = dict(self.action, goal_state="achieved", previous_result="uncertain")
        result, _ = self.evaluate(data, pending_attempt=self.action)
        self.assertEqual(result["status"], "blocked")

    def test_loading_never_recommends_a_second_launch_click(self):
        result, waiting = self.evaluate(dict(self.action, goal_state="loading"))
        self.assertTrue(waiting)
        self.assertIsNone(result["target"])

    def test_successful_effect_not_repeated_on_changed_screenshot_or_wording(self):
        previous = dict(self.action, instruction="Click Chrome", screen_signature="old")
        data = dict(self.action, instruction="Deschide Google Chrome acum", page_context="Browser loading")
        result, _ = self.evaluate(data, verified_steps=[previous])
        self.assertEqual(result["status"], "blocked")

    def test_just_verified_pending_effect_not_repeated(self):
        data = dict(self.action, previous_result="succeeded")
        result, _ = self.evaluate(data, pending_attempt=self.action)
        self.assertEqual(result["status"], "blocked")

    def test_one_failed_retry_allowed_but_not_endless_retries(self):
        data = dict(self.action, previous_result="failed")
        result, _ = self.evaluate(data, pending_attempt=self.action)
        self.assertEqual(result["status"], "action")
        result, _ = self.evaluate(data, pending_attempt=self.action, attempt_history=[self.action])
        self.assertEqual(result["status"], "blocked")

    def test_alternating_cycle_is_blocked(self):
        other = dict(self.action, control_name="Desktop", action_purpose="Revino la desktop")
        result, _ = self.evaluate(attempt_history=[self.action, other, self.action, other])
        self.assertEqual(result["status"], "blocked")

    def test_different_numbered_wizard_steps_are_allowed(self):
        previous = dict(self.action, control_name="Next", action_purpose="Open page 2")
        data = dict(self.action, control_name="Next", action_purpose="Open page 3")
        result, _ = self.evaluate(data, verified_steps=[previous])
        self.assertEqual(result["status"], "action")

    def test_missing_evidence_and_inconsistent_completion_block(self):
        for change in (dict(goal_evidence=""), dict(status="complete"), dict(goal_state="uncertain")):
            result, _ = self.evaluate(dict(self.action, **change))
            self.assertEqual(result["status"], "blocked")

    def test_schema_extension_does_not_mutate_original(self):
        schema = {"properties": {}, "required": []}
        extended = extend_schema(schema)
        self.assertIn("goal_state", extended["required"])
        self.assertEqual(schema, {"properties": {}, "required": []})


if __name__ == "__main__":
    unittest.main()
