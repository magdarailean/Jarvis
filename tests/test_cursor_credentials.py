import io
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from jarvis.features.targeting.credentials import prompt_key, check_key
from jarvis import cursor_guide
from unittest.mock import Mock


class CredentialTests(unittest.TestCase):
    def test_launcher_receives_prompted_key_in_same_process(self):
        owner = Mock()
        owner.load_api_key.side_effect = lambda: os.environ["OPENROUTER_API_KEY"]
        with patch.dict(os.environ, {}, clear=True), patch(
                "sys.argv", ["cursor_guide", "--prompt-key"]), patch(
                "jarvis.features.targeting.credentials.getpass.getpass", return_value="fake-key"), patch(
                "jarvis.cursor_guide.load_owner", return_value=owner), patch(
                "jarvis.cursor_guide.install_grounding"), patch(
                "jarvis.cursor_guide.install_progress"), patch("builtins.print"):
            cursor_guide.main()
            owner.load_api_key.assert_called_once()
            owner.main.assert_called_once()
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "fake-key")

    def test_prompt_sets_current_process_without_persisting(self):
        with patch.dict(os.environ, {}, clear=True), patch(
                "jarvis.features.targeting.credentials.getpass.getpass", return_value=" fake-test-key "):
            prompt_key()
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "fake-test-key")

    def test_empty_command_or_quoted_input_does_not_replace_key(self):
        for value in ("", "KEY=abc", "'abc'", '"abc"', "$env:OPENROUTER_API_KEY = abc", "abc\ndef"):
            with self.subTest(value=value), patch.dict(os.environ, {"OPENROUTER_API_KEY": "existing"}), patch(
                    "jarvis.features.targeting.credentials.getpass.getpass", return_value=value):
                with self.assertRaises(ValueError):
                    prompt_key()
                self.assertEqual(os.environ["OPENROUTER_API_KEY"], "existing")

    @patch("jarvis.features.targeting.credentials.urlopen")
    def test_read_only_check_does_not_reveal_response(self, request):
        request.return_value.__enter__.return_value = io.StringIO('{"data":{"label":"secret-label"}}')
        ok, message = check_key("fake-key")
        self.assertTrue(ok)
        self.assertNotIn("secret-label", message)
        self.assertEqual(request.call_args.args[0].get_method(), "GET")
        self.assertEqual(request.call_args.args[0].full_url, "https://openrouter.ai/api/v1/key")

    @patch("jarvis.features.targeting.credentials.urlopen")
    def test_authentication_network_and_malformed_response_are_distinct(self, request):
        request.side_effect = HTTPError("url", 401, "secret", {}, None)
        self.assertIn("401", check_key("fake")[1])
        request.side_effect = URLError("secret")
        self.assertIn("Cannot reach", check_key("fake")[1])
        request.side_effect = None
        request.return_value.__enter__.return_value = io.StringIO("not-json")
        self.assertIn("Could not read", check_key("fake")[1])


if __name__ == "__main__":
    unittest.main()
