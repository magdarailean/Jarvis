import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jarvis.local_config import load_local_config, speech_model
from jarvis import openrouter


class LocalSetupTests(unittest.TestCase):
    def test_allowlist_quotes_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / '.env'
            config.write_text('OPENROUTER_API_KEY="local-test"\nOPENROUTER_MODEL=test\nPATH=bad\n', encoding='utf-8-sig')
            env = {'OPENROUTER_API_KEY': 'existing'}
            load_local_config(config, env)
            self.assertEqual(env, {'OPENROUTER_API_KEY': 'existing', 'OPENROUTER_MODEL': 'test'})

    def test_missing_configuration_is_optional(self):
        env = {}
        load_local_config(Path('nonexistent-config-file'), env)
        self.assertEqual(env, {})

    def test_downloaded_model_is_discovered(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            model = root / 'models/stt/small'
            model.mkdir(parents=True)
            (model / 'model.bin').touch()
            with patch('jarvis.local_config.ROOT', root):
                self.assertEqual(speech_model('JARVIS_SPEECH_MODEL', 'small'), str(model))

    def test_missing_key_does_not_import_companion(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(openrouter, 'load_local_config'), patch('sys.argv', ['openrouter']), patch.object(openrouter.runpy, 'run_path') as run:
            self.assertEqual(openrouter.main(), 1)
            run.assert_not_called()

    def test_model_name_cannot_trigger_protected_download(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake', 'JARVIS_SPEECH_MODEL': 'small'}, clear=True), patch.object(openrouter, 'load_local_config'), patch('sys.argv', ['openrouter']), patch.object(openrouter.runpy, 'run_path') as run:
            self.assertEqual(openrouter.main(), 1)
            run.assert_not_called()
