from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tempfile
import unittest
import uuid

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.screen_capture import ScreenGeometry
from jarvis.features.screen_capture.qt_capture import capture_screen
from jarvis.features.screen_capture.session import CaptureSession
from jarvis.infrastructure.app_log import AppLog


class GeometryTests(unittest.TestCase):
    def test_mapping_actual_pixels_fractional_dpi_and_negative_origin(self):
        geometry = ScreenGeometry("left", -1536, -100, 1536, 864, 1920, 1080, 1.25)
        self.assertEqual(geometry.pixel_to_normalized(960, 540), (0.5, 0.5))
        self.assertEqual(geometry.normalized_to_desktop(0.5, 0.5), (-768, 332))
        self.assertEqual(geometry.pixel_to_normalized(1920, 1080), (1, 1))
        # Fractional scaling can round logical dimensions; actual image edges remain exact.
        rounded = replace(geometry, pixel_width=1919)
        self.assertEqual(rounded.pixel_to_normalized(1919, 1080), (1, 1))
        for point in ((-1, 0), (1921, 0), (float("nan"), 0), (0, float("inf"))):
            with self.subTest(point=point), self.assertRaises(ValueError):
                geometry.pixel_to_normalized(*point)
        with self.assertRaises(ValueError):
            geometry.normalized_to_desktop(1.01, 0)
        for change in ({"pixel_width": 0}, {"logical_height": -1}, {"device_pixel_ratio": 0}):
            with self.assertRaises(ValueError):
                replace(geometry, **change)


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def make_screen(self):
        pixmap = QPixmap(400, 200)
        pixmap.fill(QColor("#32649a"))
        pixmap.setDevicePixelRatio(1.25)
        return SimpleNamespace(geometry=lambda: QRect(-320, 0, 320, 160),
                               devicePixelRatio=lambda: 1.25, name=lambda: "fixture",
                               grabWindow=Mock(return_value=pixmap))

    def frame(self):
        return capture_screen(self.make_screen())

    def test_adapter_encodes_in_memory_with_real_pixel_dimensions(self):
        screen = self.make_screen()
        frame = capture_screen(screen)
        screen.grabWindow.assert_called_once_with(0)
        image = QImage.fromData(frame.png, "PNG")
        self.assertEqual((image.width(), image.height()), (400, 200))
        self.assertEqual(image.pixelColor(0, 0), QColor("#32649a"))
        self.assertEqual(frame.geometry.logical_width, 320)
        self.assertEqual(frame.geometry.pixel_width, 400)
        self.assertNotIn("png=", repr(frame))
        self.assertNotEqual(frame.id, self.frame().id)

    def test_adapter_rejects_unavailable_and_oversized_images(self):
        screen = self.make_screen()
        screen.grabWindow.return_value = QPixmap()
        with self.assertRaises(RuntimeError):
            capture_screen(screen)
        screen.geometry = lambda: QRect(0, 0, 10000, 10000)
        screen.grabWindow.reset_mock()
        with self.assertRaises(ValueError):
            capture_screen(screen)
        screen.grabWindow.assert_not_called()

    def test_single_activation_replacement_release_and_no_idle_capture(self):
        capture = Mock(side_effect=lambda _: self.frame())
        session = CaptureSession(capture=capture)
        try:
            QTest.qWait(30)
            capture.assert_not_called()
            self.assertTrue(session.begin(self.app.primaryScreen(), delay_ms=10))
            self.assertFalse(session.begin(self.app.primaryScreen(), delay_ms=10))
            QTest.qWait(50)
            first_id = session.frame.id
            self.assertEqual(capture.call_count, 1)
            QTest.qWait(30)
            self.assertEqual(capture.call_count, 1)
            session.begin(self.app.primaryScreen(), delay_ms=10)
            self.assertIsNone(session.frame)
            QTest.qWait(50)
            self.assertNotEqual(first_id, session.frame.id)
            session.clear()
            self.assertIsNone(session.frame)
            session.begin(self.app.primaryScreen(), delay_ms=20)
            session.clear()
            QTest.qWait(50)
            self.assertEqual(capture.call_count, 2)
        finally:
            session.clear()
            session.deleteLater()

    def test_display_change_and_removal_discard_context_and_cancel_pending_capture(self):
        capture = Mock(side_effect=lambda _: self.frame())
        session = CaptureSession(capture=capture)
        released = []
        session.frame_changed.connect(released.append)
        try:
            session.begin(self.app.primaryScreen(), delay_ms=10)
            QTest.qWait(50)
            self.assertIsNotNone(session.frame)
            session._invalidate()
            self.assertIsNone(session.frame)
            self.assertIsNone(released[-1])
            session.begin(self.app.primaryScreen(), delay_ms=20)
            session._screen_removed(self.app.primaryScreen())
            QTest.qWait(50)
            self.assertEqual(capture.call_count, 1)
        finally:
            session.clear()
            session.deleteLater()

    def test_shell_hides_capture_surfaces_restores_and_releases_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = DesktopController(self.app, instance_key=f"Jarvis.Capture.{uuid.uuid4().hex}",
                                           log=AppLog(Path(directory) / "app.log"))
            try:
                self.assertTrue(controller.start())
                controller.show_overlay_demo()

                def acquire(screen):
                    self.assertFalse(controller.window.isVisible())
                    self.assertFalse(controller.overlay.isVisible())
                    return self.frame()

                controller.capture._capture = Mock(side_effect=acquire)
                controller.window.capture_button.click()
                self.assertFalse(controller.window.isVisible())
                controller.capture._timer.start(10)
                QTest.qWait(60)
                self.assertTrue(controller.window.isVisible())
                self.assertTrue(controller.overlay.isVisible())
                self.assertTrue(controller.window.capture_preview.isVisible())
                self.assertEqual(controller.window.status.accessibleName(), "Gata")
                controller.window.capture_clear_button.click()
                self.assertIsNone(controller.capture.frame)
                self.assertTrue(controller.window.capture_preview.pixmap().isNull())
                self.assertFalse(controller.window.capture_preview.isVisible())
                controller.start_capture()
                controller.reopen_window()
                self.assertFalse(controller.capture.pending)
                self.assertIn("anulată", controller.window.capture_feedback.text())
                controller.start_capture()
                controller.close()
                QTest.qWait(30)
                self.assertFalse(controller.window.isVisible())
                self.assertIsNone(controller.capture.frame)
                self.assertEqual(controller.capture._capture.call_count, 1)
            finally:
                controller.close()
                controller.deleteLater()
                QTest.qWait(20)

    def test_capture_failure_restores_shell_even_without_tray(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = DesktopController(self.app, instance_key=f"Jarvis.Capture.{uuid.uuid4().hex}",
                                           tray_factory=Mock(side_effect=RuntimeError("no tray")),
                                           log=AppLog(Path(directory) / "app.log"))
            try:
                self.assertTrue(controller.start())
                controller.capture._capture = Mock(side_effect=RuntimeError("private details"))
                controller.start_capture()
                controller.capture._timer.start(10)
                QTest.qWait(60)
                self.assertTrue(controller.window.isVisible())
                self.assertTrue(controller.window.capture_button.isEnabled())
                self.assertIsNone(controller.capture.frame)
                self.assertEqual(controller.window.status.accessibleName(), "Eroare")
                self.assertNotIn("private details", controller.log.path.read_text())
                controller.capture._capture = Mock(return_value=self.frame())
                controller.start_capture()
                controller.capture._timer.start(10)
                QTest.qWait(60)
                self.assertIsNotNone(controller.capture.frame)
                self.assertEqual(controller.window.status.accessibleName(), "Gata")
            finally:
                controller.close()
                controller.deleteLater()
                QTest.qWait(20)
