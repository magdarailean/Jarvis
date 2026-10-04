import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from jarvis.app import DesktopController, create_application
from jarvis.features.ai.openrouter import build_payload
from jarvis.features.callouts.layout import arrange, MAX_LEADER
from jarvis.features.callouts.model import Callout, VisualKind, VisualPlan
from jarvis.features.interaction.intent import normalize, route_intent, VisualIntent
from jarvis.features.screen_capture import ScreenFrame, ScreenGeometry
from jarvis.features.session import Session
from jarvis.infrastructure.app_log import AppLog


A = 'Explică-mi cum se rezolvă ecuația aceasta.'
B = 'Arată-mi unde trebuie să apăs ca să deschid fișierul.'
C = 'Clarifică ce înseamnă formula aceasta.'


def action(kind='callout'):
    return dict(type=kind, id='equation', text='Δ=25−24=1; x=(5±1)/2, deci x=2 sau x=3.',
                target=[.35, .35, .55, .45], target_text='x² − 5x + 6 = 0',
                target_confidence=.97, placement='auto')


class IntentTests(unittest.TestCase):
    def test_normalized_romanian_and_explicit_precedence(self):
        self.assertEqual(normalize('  ARATĂ-MI,   unde să APĂS?!'), 'arata mi unde sa apas')
        cases = {
            VisualIntent.EXPLAIN: [A, C, 'Explica-mi cum deschid meniul.', 'verifică rezultatul',
                'Lămureşte formula', 'lamureste', 'calculează', 'de ce', 'cum se rezolvă?',
                'Cum rezolv ecuația aceasta?', 'Poți să îmi explici rezolvarea?',
                'Explicami cum calculez asta', 'Cum rezolvăm problema?',
                'Explică de ce accelerația depinde de forță.',
                'Verifică unitățile din problema de fizică.',
                'Clarifică ce înseamnă inerție.'],
            VisualIntent.GUIDE: ['Ajuta-ma cum sa fac o prezentare in canva.',
                'Ajută-mă să creez un document în Word.', 'Cum fac un tabel în Excel?',
                'Vreau să creez o prezentare.', 'Cum pot închide site-ul?', 'Cum pot eu să închid pagina?',
                'Cum să-l închid?', 'Cum găsesc butonul de închidere?', 'Arată-mi butonul și explică-mi ce face.',
                'Arată-mi unde să apăs', 'arata-mi unde sa apas',
                'Explică unde să apăs', B, 'Arata-mi cum sa deschid un fisier Word.', 'arată', 'unde',
                'Te rog arata-mi cum sa inchid browserul.',
                'unde găsesc', 'unde să apăs', 'cum deschid', 'cum intru', 'cum selectez',
                'cum apăs', 'cum sa salvez', 'Cum pot să deschid un fișier Word?',
                'Cum aș putea deschide meniul?', 'Îmi arăți unde găsesc fișierul?'],
            VisualIntent.AUTO: ['Cum fac problema aceasta?', 'Cum fac o omletă?', 'cum', 'Cum funcționează asta?', 'Ajută-mă.', 'aratator', ''],
        }
        for expected, phrases in cases.items():
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    self.assertEqual(route_intent(phrase), expected)

    def test_intent_restricts_outbound_schema_before_ai_selection(self):
        for phrase, kind, count in [(A, 'callout', 2), (B, 'pointer/cursor', 1), (C, 'callout', 2)]:
            request = Session().begin(phrase)
            payload = build_payload(request, [], 'test-model')
            context = json.loads(payload['messages'][1]['content'][0]['text'])
            self.assertEqual(context['visual_intent'], request.visual_intent.value)
            actions = payload['response_format']['json_schema']['schema']['properties']['actions']
            self.assertEqual(actions['maxItems'], count)
            self.assertEqual(actions['items']['properties']['type']['enum'], [kind])
        # A previous guide build must not mutate auto's shared schema.
        auto = build_payload(Session().begin('Ajută-mă'), [], 'test')
        self.assertGreater(len(auto['response_format']['json_schema']['schema']['properties']
                               ['actions']['items']['properties']['type']['enum']), 2)

    def test_bad_targets_never_escape_parser_or_discard_answer(self):
        bad = [True, '0.5', {}, [], [0, 0, 1], [0, 0, 1, 1, 1],
               [0, float('nan'), 1, 1], [0, 0, float('inf'), 1], [0, 0, 10**400, 1],
               [True, 0, 1, 1], [-.1, .2, .3, .4]]
        for target in bad:
            for kind in ('callout', 'pointer/cursor', 'arrow'):
                with self.subTest(target=str(target)[:80], kind=kind):
                    item = action(kind)
                    item['target'] = target
                    plan = VisualPlan.parse({'text': 'Answer', 'actions': [item]}, require_grounding=True)
                    self.assertEqual(plan.text, 'Answer')
                    self.assertEqual(plan.actions, ())
        for kind in ('callout', 'pointer/cursor'):
            plan = VisualPlan.parse({'text': 'Answer', 'actions': [action(kind) |
                {'target': [.8, .4, .2, .5]}]}, require_grounding=True)
            self.assertEqual(plan.actions, ())

    def test_uncertain_evidence_removes_leader_and_omits_pointer(self):
        for change in ({'target_confidence': .4}, {'target_text': ''}, {'target_confidence': True},
                       {'target_confidence': float('nan')}, {'target': [.5, .5, .5, .5]},
                       {'target': [0, 0, 1, 1]}):
            item = action() | change
            plan = VisualPlan.parse({'text': 'Answer', 'actions': [item]}, require_grounding=True)
            self.assertIsNone(plan.actions[0].target)
            item['type'] = 'pointer/cursor'
            plan = VisualPlan.parse({'text': 'Answer', 'actions': [item]}, require_grounding=True)
            self.assertEqual(plan.actions, ())


class RuntimeVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log = Path(self.temp.name)/'test.log'
        self.controller = DesktopController(self.app, log=AppLog(self.log))
        self.controller.pointer_bridge.show = Mock()
        self.controller.pointer_bridge.hide = Mock()
        screen = self.app.primaryScreen()
        r = screen.geometry()
        self.frame = ScreenFrame('current', 'now', ScreenGeometry(screen.name(), *r.getRect(),
            r.width(), r.height(), screen.devicePixelRatio()), b'fixture')
        self.controller.session.set_frame(self.frame)

    def tearDown(self):
        self.controller.close()
        self.controller.deleteLater()
        self.temp.cleanup()

    def test_a_b_c_production_boundary_enforces_route_even_if_ai_disobeys(self):
        c = self.controller
        for phrase, expected in [(A, 'explain'), (B, 'guide'), (C, 'explain')]:
            with self.subTest(phrase=phrase):
                c.pointer_bridge.show.reset_mock()
                request = c.session.begin(phrase)
                c.provider.send = Mock()
                c._submit_ai(request)
                actions = [action() | {'id': str(i)} for i in range(5)]
                actions += [action('pointer/cursor'), action('arrow')]
                c._ai_complete(request.id, {'text': 'Soluțiile sunt 2 și 3.', 'actions': actions,
                                            'guide_status': 'next', 'completion_evidence': ''})
                self.assertEqual(c.overlay.annotations, ())
                if expected == 'explain':
                    self.assertEqual(len(c.overlay.callouts), 2)
                    c.pointer_bridge.show.assert_not_called()
                    c.pointer_bridge.hide.assert_called()
                else:
                    self.assertEqual(c.overlay.callouts, ())
                    c.pointer_bridge.show.assert_called_once()
                self.assertIn('visual.intent = '+expected, self.log.read_text(encoding='utf-8'))

    def test_explain_without_valid_visuals_still_displays_answer_without_arrow(self):
        request = self.controller.session.begin(A)
        self.controller.accept_ai_response(request.id, {'text': 'x=2 sau x=3.',
            'actions': [action() | {'target': [float('nan'), 0, 1, 1]}]})
        callout, = self.controller.overlay.callouts
        self.assertEqual(callout.text, 'x=2 sau x=3.')
        self.assertIsNone(callout.target)
        layout = arrange(callout, 1280, 720)
        self.assertIsNone(layout.start)
        self.assertGreater(layout.bubble.left(), 640)

    def test_other_targets_are_protected_and_leaders_remain_nearby(self):
        item = Callout('one', 'Calculăm discriminantul.', (.35, .35, .5, .45))
        protected = [QRectF(650, 180, 350, 250)]
        layout = arrange(item, 1280, 720, protected=protected)
        self.assertIsNotNone(layout)
        self.assertFalse(layout.bubble.intersects(protected[0]))
        self.assertFalse(layout.bubble.intersects(layout.target))
        self.assertLessEqual(math.hypot(layout.start.x()-layout.end.x(),
                                       layout.start.y()-layout.end.y()), MAX_LEADER)
