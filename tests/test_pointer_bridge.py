import importlib.util
import time
import unittest

from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import create_application
from jarvis.features.callouts.model import VisualAction, VisualKind
from jarvis.infrastructure.pointer_bridge import PointerBridge


class PointerBridgeTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PyQt6'), 'Cursor worker requires PyQt6')
    def test_real_worker_confirms_pointer_then_closes(self):
        app = QApplication.instance() or create_application()
        bridge = PointerBridge()
        shown, errors = [], []
        bridge.shown.connect(lambda: shown.append(True))
        bridge.failed.connect(errors.append)
        try:
            bridge.show(VisualAction(VisualKind.POINTER, 'test', (.45, .45, .5, .5)),
                        app.primaryScreen())
            deadline = time.monotonic() + 8
            while not shown and not errors and time.monotonic() < deadline:
                QTest.qWait(20)
            self.assertEqual(errors, [])
            self.assertEqual(shown, [True])
            bridge.hide()
            self.assertIsNone(bridge.pending)
        finally:
            bridge.close()
        self.assertEqual(bridge.process.state(), QProcess.ProcessState.NotRunning)
