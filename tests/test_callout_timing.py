from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from jarvis.app import DesktopController, create_application
from jarvis.features.callouts.model import Callout, VisualPlan
from jarvis.features.callouts.layout import arrange
from jarvis.features.callouts.timing import CalloutTiming
from jarvis.features.callouts.window import paint_callout
from jarvis.features.overlay.model import Annotation, Shape
from jarvis.features.overlay.window import OverlayWindow
from jarvis.infrastructure.app_log import AppLog


class CalloutTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.now = [0.0]
        self.overlay = OverlayWindow(self.app.primaryScreen())
        self.overlay.callout_timing.clock = lambda: self.now[0]

    def tearDown(self):
        self.overlay.close()
        self.overlay.deleteLater()

    def add(self):
        self.overlay.apply_visual_plan(VisualPlan.parse({'text': 'Answer', 'actions': [
            {'type': 'callout', 'id': 'one', 'text': 'O explicație suficient de lungă.', 'target': [.4, .4, .5, .5]}]}))

    def test_progress_expiry_20_seconds_and_safe_repeat_removal(self):
        self.add()
        timing = self.overlay.callout_timing
        self.assertEqual(timing.count('one'), 0)
        self.now[0] = .12
        self.assertGreater(timing.count('one'), 0)
        self.assertLess(timing.count('one'), len(self.overlay.callouts[0].text))
        self.now[0] = 19.99
        timing.tick()
        self.assertEqual(len(self.overlay.callouts), 1)
        self.now[0] = 20.01
        timing.tick()
        self.assertEqual(self.overlay.callouts, ())
        self.assertFalse(timing.timer.isActive())
        timing.tick()
        self.overlay.remove('one')
        self.assertEqual(timing.entries, {})

    def test_removed_animation_update_and_hidden_overlay(self):
        self.add()
        self.now[0] = 10
        self.add()  # Same ID resets its lifetime/animation.
        self.now[0] = 20.1
        self.overlay.callout_timing.tick()
        self.assertEqual(len(self.overlay.callouts), 1)
        self.overlay.upsert(Annotation('keep', Shape.RECTANGLE, (.1, .1, .2, .2)))
        self.overlay.hide()
        self.now[0] = 31
        self.overlay.callout_timing.tick()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(len(self.overlay.annotations), 1)
        self.add()
        self.overlay.remove('one')
        self.assertFalse(self.overlay.callout_timing.timer.isActive())

    def test_push_to_talk_clears_only_temporary_before_listening(self):
        self.add()
        self.overlay.upsert(Annotation('keep', Shape.RECTANGLE, (.1, .1, .2, .2)))
        persistent = Callout('future', 'Persistent API option', temporary=False)
        self.overlay._callouts.upsert(persistent)
        self.overlay.callout_timing.start(persistent)
        pointer_cleared = Mock()
        self.overlay.pointer_cleared.connect(pointer_cleared)
        with tempfile.TemporaryDirectory() as folder:
            controller = DesktopController(self.app, log=AppLog(Path(folder)/'test.log'))
            controller.overlay = self.overlay
            def press(*_):
                self.assertEqual([c.id for c in self.overlay.callouts], ['future'])
                self.assertEqual(len(self.overlay.annotations), 1)
                pointer_cleared.assert_not_called()
            controller.interaction = SimpleNamespace(active=False, press=press, close=lambda: None)
            try:
                controller._push_to_talk()
            finally:
                controller.overlay = None
                controller.close()
        self.now[0] = 40
        self.overlay.callout_timing.tick()
        self.assertEqual([c.id for c in self.overlay.callouts], ['future'])

    def test_renderer_reveals_glyphs_without_changing_bounds(self):
        item = Callout('render', 'Explicație progresivă.', (.2, .3, .3, .4))
        layout = arrange(item, 800, 600)
        images = []
        for count in (0, 8, len(item.text)):
            image = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor('transparent'))
            painter = QPainter(image)
            paint_callout(painter, item, layout, count)
            painter.end()
            rect = layout.bubble.adjusted(16, 16, -16, -16).toRect()
            white = sum(image.pixelColor(x, y).lightness() > 180
                        for y in range(rect.top(), rect.bottom()+1)
                        for x in range(rect.left(), rect.right()+1))
            images.append(white)
        self.assertEqual(images[0], 0)
        self.assertGreater(images[1], images[0])
        self.assertGreater(images[2], images[1])

    def test_real_qt_timer_expires_and_stops(self):
        timing = CalloutTiming(lifetime=.08)
        expired = []
        timing.expired.connect(expired.append)
        timing.start(Callout('timer', 'Test'))
        QTest.qWait(140)
        self.assertEqual(expired, ['timer'])
        self.assertFalse(timing.timer.isActive())
        timing.clear()
