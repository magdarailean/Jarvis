import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QLocale, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from jarvis.app import DesktopController, create_application
from jarvis.infrastructure.app_log import AppLog
from jarvis.infrastructure.single_instance import SingleInstance
from jarvis.infrastructure.tray import TrayIcon


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.key = f"Jarvis.Test.{uuid.uuid4().hex}"
        self.temporary = tempfile.TemporaryDirectory()
        self.log = AppLog(Path(self.temporary.name) / "application.log")
        self.controllers = []

    def tearDown(self):
        for controller in self.controllers:
            controller.close()
            controller.deleteLater()
        QTest.qWait(20)
        self.temporary.cleanup()

    def start(self, **kwargs):
        controller = DesktopController(self.app, instance_key=self.key, log=self.log, **kwargs)
        self.controllers.append(controller)
        self.assertTrue(controller.start())
        QTest.qWait(30)
        return controller

    def wait_until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertTrue(condition(), "Condition did not become true before timeout")

    def duplicate(self):
        process = subprocess.Popen([sys.executable, "-m", "tests.peer", "duplicate", self.key],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.wait_until(lambda: process.poll() is not None, timeout=10)
            output, errors = process.communicate(timeout=2)
            self.assertEqual(process.returncode, 0, (output, errors))
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_shell_layout_hide_close_reopen_and_minimized_restore(self):
        controller = self.start()
        window = controller.window
        self.assertTrue(window.isVisible())
        self.assertEqual(QLocale().name(), "ro_RO")
        self.assertEqual(window.windowTitle(), "Jarvis — Asistent și tutore")
        self.assertTrue(window.hide_button.isEnabled())
        artifacts = Path(".artifacts")
        artifacts.mkdir(exist_ok=True)
        self.assertTrue(window.grab().save(str(artifacts / "python-shell-normal.png")))
        window.resize(500, 480)
        QTest.qWait(30)
        self.assertTrue(window.rect().contains(window.exit_button.geometry()))
        self.assertTrue(window.grab().save(str(artifacts / "python-shell-minimum.png")))
        window.resize(720, 640)

        # QtTest delivers actual widget mouse/key events, not only signal calls.
        QTest.mouseClick(window.hide_button, Qt.MouseButton.LeftButton)
        self.assertFalse(window.isVisible())
        self.duplicate()
        self.wait_until(window.isVisible)
        window.close()
        self.assertFalse(window.isVisible())
        self.assertFalse(controller._closed)
        self.duplicate()
        self.wait_until(window.isVisible)
        window.showMinimized()
        self.duplicate()
        self.wait_until(lambda: not window.isMinimized())
        window.hide_button.setFocus()
        QTest.keyClick(window.hide_button, Qt.Key.Key_Tab)
        self.assertTrue(window.exit_button.hasFocus())
        QTest.keyClick(window.exit_button, Qt.Key.Key_Return)
        self.assertTrue(controller._closed)
        self.assertFalse(controller.tray.icon.isVisible())
        replacement = SingleInstance(self.key)
        try:
            self.assertTrue(replacement.is_primary)
        finally:
            replacement.close()
        self.assertIn("Application stopped; exitCode=0", self.log.path.read_text(encoding="utf-8"))

    def test_native_tray_actions_and_double_click_signal(self):
        controller = self.start()
        tray, window = controller.tray, controller.window
        self.assertEqual(tray.status_action.text(), "Gata · Microfon oprit")
        self.assertFalse(tray.status_action.isEnabled())
        window.hide_to_tray()
        tray.open_action.trigger()
        self.assertTrue(window.isVisible())
        window.hide_to_tray()
        tray.icon.activated.emit(QSystemTrayIcon.ActivationReason.DoubleClick)
        self.assertTrue(window.isVisible())
        tray.exit_action.trigger()
        self.assertTrue(controller._closed)

    def test_tray_initialization_failure_keeps_window_usable(self):
        def unavailable(*_):
            raise RuntimeError("Simulated missing tray")

        controller = self.start(tray_factory=unavailable)
        self.assertFalse(controller.window.hide_button.isEnabled())
        self.assertTrue(controller.window.tray_error.isVisible())
        controller.window.close()
        self.assertTrue(controller._closed)

    def test_system_tray_availability_is_checked(self):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            with self.assertRaises(RuntimeError):
                TrayIcon(lambda: None, lambda: None)

    def test_real_event_loop_exits_and_restarts(self):
        for _ in range(2):
            result = subprocess.run([sys.executable, "-m", "tests.peer", "cycle", self.key],
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_worker_stops_and_late_activation_cannot_reopen(self):
        controller = self.start()
        controller.activation_requested.emit()
        controller.close()
        QTest.qWait(30)
        self.assertFalse(controller.window.isVisible())
        self.assertIsNone(controller.instance._thread)

    def test_crashed_primary_does_not_block_restart(self):
        process = subprocess.Popen([sys.executable, "-m", "tests.peer", "crash", self.key],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ready = threading.Event()
        lines = []

        def read_ready():
            lines.append(process.stdout.readline())
            ready.set()

        reader = threading.Thread(target=read_ready, daemon=True)
        reader.start()
        try:
            self.assertTrue(ready.wait(10), "Child did not initialize")
            self.assertEqual(lines[0].strip(), b"READY")
            # Kill the interpreter itself, not Windows' venv redirector parent.
            process.communicate(input=b"crash\n", timeout=5)
            self.assertEqual(process.returncode, 23)
            replacement = SingleInstance(self.key)
            try:
                self.assertTrue(replacement.is_primary)
            finally:
                replacement.close()
        finally:
            if process.poll() is None:
                process.kill()
            reader.join(timeout=5)
            process.communicate(timeout=5)

    def test_installed_launchers_notify_existing_instance(self):
        # Uses the real per-user namespace, but never closes an existing user app.
        instance = SingleInstance()
        try:
            if not instance.is_primary:
                self.skipTest("Close running Jarvis before checking installed launchers")
            activated = threading.Event()
            instance.listen(activated.set)
            launcher = Path(sys.executable).parent / "jarvis.exe"
            for command in ([sys.executable, "-m", "jarvis"], [str(launcher)]):
                activated.clear()
                result = subprocess.run(command, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(activated.wait(3))
        finally:
            instance.close()


if __name__ == "__main__":
    unittest.main()
