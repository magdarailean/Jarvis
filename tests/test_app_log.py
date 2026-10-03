import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.infrastructure.app_log import AppLog


class AppLogTests(unittest.TestCase):
    def test_writes_and_resets_at_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logs" / "application.log"
            log = AppLog(path)
            log.write("Application starting.")
            self.assertIn("Application starting.", path.read_text(encoding="utf-8"))
            path.write_text("x" * AppLog.MAX_BYTES, encoding="utf-8")
            log.write("Application stopped.")
            self.assertLess(path.stat().st_size, 1024)
            self.assertIn("Application stopped.", path.read_text(encoding="utf-8"))

    def test_denied_disk_and_missing_console_do_not_raise(self):
        with patch.object(Path, "mkdir", side_effect=PermissionError), patch("sys.stderr", None):
            AppLog().write("Application starting.")


if __name__ == "__main__":
    unittest.main()
