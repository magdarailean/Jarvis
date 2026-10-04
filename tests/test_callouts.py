from dataclasses import replace
import random
import unittest

from PySide6.QtCore import Qt, QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from jarvis.app import create_application

from jarvis.features.callouts.model import Callout, CalloutScene, VisualPlan
from jarvis.features.callouts.layout import arrange
from jarvis.features.callouts.window import CalloutOverlay
from jarvis.features.callouts.demo import CASES


class CalloutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def test_malformed_actions_preserve_answer_and_valid_siblings(self):
        actions = [None, {}, {"type": "pointer/cursor"}, {"type": "none"},
                   {"type": "callout", "id": "bad", "text": "x", "target": [0, float('nan'), 1, 1]},
                   {"type": "callout", "id": "good", "text": "Explicație", "target": [.3, .3, .4, .4]}]
        plan = VisualPlan.parse({"text": "Răspuns păstrat", "actions": actions})
        self.assertEqual(plan.text, "Răspuns păstrat")
        self.assertEqual(len(plan.actions), 2)  # Explicit none plus the valid callout.
        self.assertEqual(VisualPlan.parse({"text": "General"}).actions, ())
        for change in ({"text": ""}, {"id": "bad id"}, {"target": (0, 0, -1, 1)},
                       {"placement": []}, {"text": "a"*2001}, {"visible": 1}):
            with self.assertRaises(ValueError):
                replace(CASES[0], **change)

    def test_stable_ids_lifecycle_and_capacity(self):
        scene = CalloutScene()
        item = CASES[0]
        scene.upsert(item)
        scene.upsert(replace(item, text="Actualizat"))
        scene.highlight(item.id)
        self.assertEqual(len(scene.items), 1)
        self.assertEqual(scene.items[0].text, "Actualizat")
        self.assertTrue(scene.items[0].highlighted)
        for index in range(15):
            scene.upsert(replace(item, id=str(index)))
        with self.assertRaises(ValueError):
            scene.upsert(replace(item, id="overflow"))
        scene.remove(item.id)
        scene.clear()
        self.assertEqual(scene.items, ())

    def assert_safe(self, layout, width, height):
        self.assertTrue(QRectF(0, 0, width, height).contains(layout.bubble))
        if layout.target is not None:
            self.assertFalse(layout.bubble.intersects(layout.target))
            self.assertFalse(layout.bubble.contains(layout.target.center()))
            self.assertTrue(layout.bubble.adjusted(-.01, -.01, .01, .01).contains(layout.start))
            self.assertTrue(layout.target.adjusted(-.01, -.01, .01, .01).contains(layout.end))
        self.assertLessEqual(layout.text.size().height()+32, layout.bubble.height())

    def test_center_edges_long_text_and_point_at_multiple_sizes(self):
        for width, height in ((800, 600), (1280, 720), (1920, 1080), (2560, 1440)):
            for item in CASES:
                with self.subTest(size=(width, height), case=item.id):
                    layout = arrange(item, width, height)
                    self.assertIsNotNone(layout)
                    self.assert_safe(layout, width, height)

    def test_random_regions_never_force_overlap_or_offscreen(self):
        rng = random.Random(42)
        for _ in range(300):
            x1, x2 = sorted((rng.random(), rng.random()))
            y1, y2 = sorted((rng.random(), rng.random()))
            layout = arrange(replace(CASES[0], target=(x1, y1, x2, y2)), 1024, 768)
            if layout is not None:
                self.assert_safe(layout, 1024, 768)
        self.assertIsNone(arrange(replace(CASES[0], target=(0, 0, 1, 1)), 1024, 768))
        self.assertIsNone(arrange(CASES[0], 20, 20))
        plain = arrange(replace(CASES[0], target=None), 1024, 768)
        self.assertIsNone(plain.start)
        for side in ("left", "right", "above", "below"):
            layout = arrange(replace(CASES[0], placement=side), 1920, 1080)
            self.assert_safe(layout, 1920, 1080)
        unbroken = arrange(replace(CASES[0], text="W"*300), 1920, 1080)
        self.assert_safe(unbroken, 1920, 1080)

    def test_real_window_transparency_persistence_and_display_invalidation(self):
        overlay = CalloutOverlay(self.app.primaryScreen())
        try:
            overlay.upsert(CASES[0])
            QTest.qWait(100)
            self.assertTrue(overlay.isVisible())
            self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
            rendered = overlay.grab().toImage()
            self.assertEqual(rendered.pixelColor(0, 0).alpha(), 0)
            layout = arrange(CASES[0], overlay.width(), overlay.height())
            ratio = rendered.devicePixelRatio()
            self.assertGreater(rendered.pixelColor(int(layout.bubble.center().x()*ratio), int(layout.bubble.center().y()*ratio)).alpha(), 200)
            overlay.highlight(CASES[0].id)
            self.assertEqual(len(overlay.scene.items), 1)
            overlay.invalidate()
            self.assertFalse(overlay.isVisible())
            self.assertEqual(overlay.scene.items, ())
        finally:
            overlay.close()
            overlay.deleteLater()
