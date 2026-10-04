from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.callouts.model import VisualPlan, VisualKind
from jarvis.features.callouts.layout import arrange
from jarvis.features.callouts.model import Callout
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.infrastructure.app_log import AppLog


class VisualResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = DesktopController(self.app, log=AppLog(Path(self.temp.name)/'test.log'))
        screen = self.app.primaryScreen()
        rect = screen.geometry()
        self.geometry = ScreenGeometry(screen.name(), rect.x(), rect.y(), rect.width(), rect.height(),
                                       rect.width(), rect.height(), screen.devicePixelRatio())
        self.controller.session.set_frame(ScreenFrame('frame', 'now', self.geometry, b'fixture'))
        self.answers = []
        self.controller.answer_ready.connect(self.answers.append)

    def tearDown(self):
        self.controller.close()
        self.controller.deleteLater()
        self.temp.cleanup()

    def respond(self, actions, question='Ajută-mă aici.'):
        request = self.controller.session.begin(question)
        self.assertTrue(self.controller.accept_ai_response(request.id, {'text': 'Răspuns normal.', 'actions': actions}))
        return request

    def test_real_overlay_callout_has_no_artificial_target_and_preserves_text(self):
        self.respond([{'type': 'callout', 'id': 'step1', 'text': 'Aici.', 'target': [.4, .4, .5, .5],
                       'target_text': 'x + 3', 'target_confidence': .95}])
        overlay = self.controller.overlay
        self.assertEqual(overlay.annotations, ())
        self.assertEqual(len(overlay.callouts), 1)
        self.assertTrue(overlay.has_visuals)
        layout = arrange(overlay.callouts[0], overlay.width(), overlay.height())
        image = overlay.grab().toImage()
        ratio = image.devicePixelRatio()
        target = layout.target.center()
        self.assertEqual(image.pixelColor(int(target.x()*ratio), int(target.y()*ratio)).alpha(), 0)
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(self.answers, ['Răspuns normal.'])
        self.assertEqual(self.controller.session.turns[-1].explanation, 'Răspuns normal.')
        self.respond([])
        self.assertEqual(len(overlay.callouts), 1)  # No new action does not erase persisted visuals.
        self.controller.end_session()
        self.assertIsNone(self.controller.overlay)

    def test_none_invalid_visuals_and_stale_responses(self):
        request = self.respond([{'type': 'none'}, {'type': 'nonsense'}, {'type': 'callout', 'text': 'missing ID'}])
        self.assertIsNone(self.controller.overlay)
        self.assertFalse(self.controller.accept_ai_response(request.id, {'text': 'Late'}))
        self.assertEqual(len(self.answers), 1)

    def test_auto_pointer_starts_exclusive_guide_session(self):
        pointers = []
        self.controller.pointer_requested.connect(pointers.append)
        actions = [{'type': kind, 'id': kind, 'target': [.1, .2, .3, .4],
                    'target_text': 'visible item', 'target_confidence': .95}
                   for kind in ('highlight', 'arrow', 'rectangle', 'circle', 'line')]
        actions.append({'type': 'pointer/cursor', 'id': 'pointer', 'target': [.5, .5, .6, .6],
                        'target_text': 'Open', 'target_confidence': .95})
        self.respond(actions)
        self.assertEqual(len(self.controller.overlay.annotations), 0)
        self.assertTrue(self.controller.guide.active)
        self.assertEqual(len(pointers), 1)
        self.assertEqual(pointers[0].kind, VisualKind.POINTER)
        self.assertEqual(self.controller.overlay.callouts, ())

    def test_render_failure_and_missing_context_keep_answer(self):
        with patch('jarvis.app.OverlayWindow', side_effect=RuntimeError('No renderer')):
            self.respond([{'type': 'callout', 'id': 'x', 'text': 'Text'}])
        self.assertEqual(len(self.answers), 1)
        self.controller.session.set_frame(None)
        self.respond([{'type': 'callout', 'id': 'x', 'text': 'Text'}])
        self.assertIsNone(self.controller.overlay)

    def test_compact_size_scales_with_content(self):
        small = arrange(Callout('one', 'Aici.'), 1280, 720)
        long = arrange(Callout('two', 'Aceasta este o explicație mai lungă. '*8), 1280, 720)
        self.assertLess(small.bubble.width(), 200)
        self.assertGreater(long.bubble.height(), small.bubble.height())
        self.assertLessEqual(long.bubble.width(), 360)
        second = arrange(Callout('three', 'Alt pas.'), 1280, 720, [small.bubble])
        self.assertFalse(small.bubble.intersects(second.bubble))
