from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import ctypes
import tempfile
import unittest
import uuid
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.overlay import Annotation, AnnotationScene, Shape
from jarvis.features.overlay.demo import demo_annotations
from jarvis.features.overlay.window import OverlayWindow
from jarvis.infrastructure.app_log import AppLog


class AnnotationTests(unittest.TestCase):
    def test_rejects_invalid_geometry_and_unbounded_input(self):
        for bounds in ((0, 0, float("nan"), 1), (0, 0, float("inf"), 1),
                       (-0.1, 0, 1, 1), (0, 0, 1.1, 1), (0.5, 0, 0.1, 1),
                       (0, 0, 0, 1), (True, 0, 1, 1), [0, 0, 1, 1]):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                Annotation("test", Shape.RECTANGLE, bounds)
        valid = Annotation("step-1", Shape.LABEL, (0, 0, 1, 1), "Pasul întâi")
        for change in ({"id": ""}, {"id": "x" * 65}, {"shape": "unknown"},
                       {"text": " "}, {"text": "x" * 201}, {"visible": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(valid, **change)
        with self.assertRaises(ValueError):
            Annotation("line", Shape.ARROW, (0.5, 0.5, 0.5, 0.5))
        # Reversed endpoints are useful for arrows pointing up/left.
        Annotation("line", Shape.ARROW, (0.9, 0.9, 0.1, 0.1))

    def test_stable_ids_visibility_highlight_capacity_and_clear(self):
        scene = AnnotationScene()
        item = Annotation("one", Shape.RECTANGLE, (0.1, 0.1, 0.5, 0.5))
        scene.upsert(item)
        snapshot = scene.annotations
        scene.upsert(replace(item, bounds=(0.2, 0.2, 0.6, 0.6)))
        scene.set_visible("one", False)
        scene.highlight("one")
        self.assertEqual(len(scene.annotations), 1)
        self.assertFalse(scene.annotations[0].visible)
        self.assertTrue(scene.annotations[0].highlighted)
        self.assertEqual(snapshot, (item,))
        with self.assertRaises(FrozenInstanceError):
            item.visible = False
        for index in range(63):
            scene.upsert(replace(item, id=f"id-{index}"))
        scene.upsert(item)  # Updates remain allowed at capacity.
        with self.assertRaises(ValueError):
            scene.upsert(replace(item, id="overflow"))
        scene.remove("one")
        scene.remove("missing")
        with self.assertRaises(KeyError):
            scene.highlight("missing")
        scene.clear()
        self.assertEqual(scene.annotations, ())


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def test_render_input_flags_persistence_and_display_invalidation(self):
        overlay = OverlayWindow(self.app.primaryScreen())
        try:
            self.assertFalse(overlay.isVisible())
            for item in demo_annotations():
                overlay.upsert(item)
            QTest.qWait(50)
            self.assertTrue(overlay.isVisible())
            self.assertEqual(overlay.geometry(), self.app.primaryScreen().geometry())
            for flag in (Qt.WindowType.WindowTransparentForInput,
                         Qt.WindowType.WindowDoesNotAcceptFocus,
                         Qt.WindowType.WindowStaysOnTopHint):
                self.assertTrue(overlay.windowFlags() & flag)
            self.assertTrue(overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
            # Verify Qt actually applied native transparency/topmost styles on Windows.
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.GetWindowLongW.restype = ctypes.c_long
            native_style = user32.GetWindowLongW(int(overlay.winId()), -20)
            for flag in (0x20, 0x80000, 0x8):  # TRANSPARENT, LAYERED, TOPMOST
                self.assertTrue(native_style & flag)
            rendered = overlay.grab()  # Widget render only; never a desktop capture.
            image = rendered.toImage()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            self.assertEqual(image.pixelColor(int(image.width() * 0.2),
                                             int(image.height() * 0.3)).alpha(), 45)
            artifacts = Path(".artifacts")
            artifacts.mkdir(exist_ok=True)
            self.assertTrue(rendered.save(str(artifacts / "overlay-demo.png")))
            QTest.qWait(50)
            self.assertEqual(len(overlay.annotations), 6)
            overlay.highlight("demo-box")
            overlay.set_visible("demo-circle", False)
            overlay.remove("demo-line")
            self.assertEqual(len(overlay.annotations), 5)
            overlay._display_changed()
            self.assertEqual(overlay.annotations, ())
            self.assertFalse(overlay.isVisible())
            overlay.upsert(demo_annotations()[0])
            overlay._screen_removed(self.app.primaryScreen())
            self.assertFalse(overlay.isVisible())
            with self.assertRaises(RuntimeError):
                overlay.upsert(demo_annotations()[0])
        finally:
            overlay.close()
            overlay.deleteLater()
            QTest.qWait(10)

    def test_shell_demo_clear_reopen_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = DesktopController(self.app, instance_key=f"Jarvis.OverlayTest.{uuid.uuid4().hex}",
                                           log=AppLog(Path(directory) / "app.log"))
            try:
                self.assertTrue(controller.start())
                controller.window.overlay_demo_button.click()
                first = controller.overlay
                self.assertTrue(first.isVisible())
                controller.window.hide_to_tray()
                self.assertTrue(first.isVisible())
                controller.reopen_window()
                controller.window.overlay_demo_button.click()
                self.assertFalse(first.isVisible())
                self.assertIsNot(controller.overlay, first)
                controller.window.overlay_clear_button.click()
                self.assertIsNone(controller.overlay)
                with patch("jarvis.app.OverlayWindow", side_effect=RuntimeError("Unavailable")):
                    controller.show_overlay_demo()
                self.assertIsNone(controller.overlay)
                self.assertIn("nu pot fi afișate", controller.window.overlay_feedback.text())
                self.assertFalse(controller._closed)
                controller.show_overlay_demo()
                last = controller.overlay
                controller.close()
                self.assertFalse(last.isVisible())
                self.assertEqual(last.annotations, ())
                controller.show_overlay_demo()
                self.assertIsNone(controller.overlay)
            finally:
                controller.close()
                controller.deleteLater()
                QTest.qWait(20)
