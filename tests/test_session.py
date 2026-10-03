from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest
import uuid

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.overlay import Annotation, Shape
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.features.session import AssistantMode, Session
from jarvis.infrastructure.app_log import AppLog


class SessionTests(unittest.TestCase):
    def test_followups_include_successful_explanations_mode_and_visual_snapshot(self):
        session = Session()
        geometry = ScreenGeometry("test", 0, 0, 100, 100, 100, 100, 1)
        frame = ScreenFrame("image", "now", geometry, b"test-image")
        session.set_frame(frame)
        session.mode = AssistantMode.TUTOR
        marks = (Annotation("step-2", Shape.RECTANGLE, (0, 0, 0.5, 0.5)),)
        first = session.begin("  Explică problema.  ", marks)
        self.assertEqual(first.question, "Explică problema.")
        self.assertIs(first.frame, frame)
        self.assertEqual(first.annotations, marks)
        self.assertEqual(first.mode, AssistantMode.TUTOR)
        self.assertTrue(session.complete(first.id, "Pasul 2: împarte la doi."))
        followup = session.begin("De ce pasul doi?", marks)
        self.assertEqual(followup.history[0].explanation, "Pasul 2: împarte la doi.")
        self.assertEqual(followup.history[0].frame_id, "image")
        self.assertFalse(hasattr(followup.history[0], "frame"))
        with self.assertRaises(FrozenInstanceError):
            followup.question = "changed"

    def test_bounded_whole_turns_and_local_failures_excluded_from_ai_history(self):
        session = Session()
        for index in range(20):
            request = session.begin(str(index))
            session.complete(request.id, "Un răspuns.")
        self.assertEqual(len(session.turns), 12)
        self.assertEqual(session.turns[0].question, "8")
        request = session.begin("Indisponibil?")
        session.fail(request.id, "Serviciu indisponibil.")
        next_request = session.begin("Mai simplu.")
        self.assertEqual(len(next_request.history), 11)
        self.assertTrue(all(turn.explanation is not None for turn in next_request.history))
        session.end()
        for _ in range(12):
            request = session.begin("q" * 2000)
            session.complete(request.id, "a" * 12000)
        self.assertLess(len(session.turns), 12)
        self.assertLessEqual(sum(len(t.question) + len(t.explanation) for t in session.turns),
                             Session.MAX_HISTORY_CHARS)

    def test_validation_does_not_mutate_history_and_duplicate_requests_are_rejected(self):
        session = Session()
        for value in ("", "   ", "x" * 2001):
            with self.assertRaises(ValueError):
                session.begin(value)
            self.assertIsNone(session.pending)
        request = session.begin("Întrebare")
        with self.assertRaises(RuntimeError):
            session.begin("Alta")
        for value in ("", "x" * 12001):
            with self.assertRaises(ValueError):
                session.complete(request.id, value)
        self.assertEqual(session.turns, ())
        self.assertTrue(session.complete(request.id, "Răspuns valid"))
        self.assertFalse(session.complete(request.id, "Răspuns duplicat"))

    def test_released_context_and_ended_session_reject_late_responses(self):
        session = Session()
        request = session.begin("Veche")
        session.set_frame(None)
        self.assertFalse(session.complete(request.id, "Prea târziu"))
        newer = session.begin("Nouă")
        old_id = session.id
        session.end()
        self.assertNotEqual(old_id, session.id)
        self.assertIsNone(session.frame)
        self.assertIsNone(session.pending)
        self.assertFalse(session.fail(newer.id, "Eroare întârziată"))
        self.assertEqual(session.turns, ())


class SessionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def test_typed_fallback_plain_text_mode_retention_and_end_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = DesktopController(self.app, instance_key=f"Jarvis.Session.{uuid.uuid4().hex}",
                                           log=AppLog(Path(directory) / "app.log"))
            try:
                self.assertTrue(controller.start())
                panel = controller.window.session_panel
                panel.send.click()
                self.assertEqual(controller.session.turns, ())
                self.assertIn("Scrie", panel.feedback.text())
                panel.mode.setCurrentIndex(1)
                panel.question.setText("<b>Întrebare privată</b>")
                QTest.keyClick(panel.question, Qt.Key.Key_Return)
                self.assertEqual(len(controller.session.turns), 1)
                self.assertEqual(controller.session.turns[0].mode, AssistantMode.SOLVE)
                self.assertIsNone(controller.session.turns[0].explanation)
                self.assertIn("<b>Întrebare privată</b>", panel.history.toPlainText())
                self.assertIn("Stare serviciu", panel.history.toPlainText())
                controller.window.scroll.ensureWidgetVisible(panel.question)
                QTest.qWait(20)
                Path(".artifacts").mkdir(exist_ok=True)
                self.assertTrue(controller.window.grab().save(".artifacts/session-typed.png"))
                self.assertNotIn("Întrebare privată", controller.log.path.read_text(encoding="utf-8"))
                controller.window.hide_to_tray()
                controller.reopen_window()
                self.assertEqual(len(controller.session.turns), 1)
                controller.show_overlay_demo()
                controller.start_capture()
                panel.question.setText("Schiță netrimisă")
                panel.end_button.click()
                self.assertFalse(controller.capture.pending)
                self.assertIsNone(controller.capture.frame)
                self.assertIsNone(controller.session.frame)
                self.assertIsNone(controller.overlay)
                self.assertEqual(controller.session.turns, ())
                self.assertEqual(panel.history.toPlainText(), "")
                self.assertEqual(panel.question.text(), "")
                self.assertEqual(panel.mode.currentData(), AssistantMode.EXPLAIN)
                self.assertTrue(controller.window.isVisible())
                panel.question.setText("O nouă sesiune")
                panel.send.click()
                self.assertEqual(len(controller.session.turns), 1)
                controller.close()
                self.assertEqual(controller.session.turns, ())
                self.assertEqual(panel.history.toPlainText(), "")
            finally:
                controller.close()
                controller.deleteLater()
                QTest.qWait(20)
