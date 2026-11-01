"""On-demand recipes: catalog, user-facing card and coordinator index."""
import copy
import json
import unittest
from pathlib import Path

from righaven import gallery, recipes, state

ROOT = Path(__file__).resolve().parents[1]


class RecipeCatalog(unittest.TestCase):
    def test_every_recipe_has_its_skill_tools_and_preset(self):
        from righaven.environments import PRESETS
        known = {a['id'] for a in state.applications()}
        presets = {p['id']: p for p in PRESETS}
        for recipe in recipes.recipes():
            self.assertTrue((ROOT / 'skills/custom' / recipe['skill'] / 'SKILL.md').is_file(), recipe['skill'])
            self.assertLessEqual(set(recipe['tools']), known)
            self.assertIn(recipe['skill'], presets[recipe['environment']].get('skills', []))
            self.assertIn(recipe['skill'], gallery.MANAGED_SKILLS, 'recipe skills are shareable managed skills')

    def test_card_tells_what_to_attach_what_is_asked_and_what_you_get(self):
        for locale, phrase in (('it-IT', 'Usa la ricetta'), ('en-US', 'Use the')):
            card = recipes.detail('data-pipeline', locale)
            self.assertTrue(card['attach_required'] and card['outputs'] and card['questions'])
            self.assertEqual(card['starter'], '', 'guided intake replaces bracketed prompts')
            self.assertTrue(any(p['checkpoint'] for p in card['phases']))
            self.assertTrue(any('password' in item.lower() or 'credenzial' in item.lower() for item in card['attach_never']))
        self.assertEqual([p['checkpoint'] for p in recipes.detail('data-pipeline', 'it')['phases']],
                         [p['checkpoint'] for p in recipes.detail('data-pipeline', 'en')['phases']])

    def test_coordinator_index_lists_only_authorized_recipes(self):
        everything = recipes.coordinator_index()
        self.assertEqual([r['id'] for r in everything], ['data-pipeline'])
        self.assertEqual(recipes.coordinator_index({'skill-harness'}), [])
        row = recipes.coordinator_index({'skill-data-pipeline'})[0]
        self.assertEqual(row['skill'], 'skill-data-pipeline')
        self.assertIn('Comprensione e catalogo', row['checkpoints'])
        self.assertLess(len(json.dumps(everything, ensure_ascii=False)), 4000, 'compact enough for every coordinator turn')

    def test_unknown_recipe_and_invalid_definitions_are_rejected(self):
        with self.assertRaises(ValueError):
            recipes.detail('non-esiste')
        base = copy.deepcopy(recipes.recipes()[0])
        broken = copy.deepcopy(base);broken['tools'] = ['programma-inesistente']
        with self.assertRaises(ValueError):
            recipes.validate(broken, {a['id'] for a in state.applications()})
        broken = copy.deepcopy(base);broken['en']['phases'] = broken['en']['phases'][:1]
        with self.assertRaises(ValueError):
            recipes.validate(broken)
        broken = copy.deepcopy(base);broken['it']['attach_required'] = []
        with self.assertRaises(ValueError):
            recipes.validate(broken)

    def test_frontend_offers_the_recipe_page_and_prefilled_chat(self):
        docker = (ROOT / 'docker/Dockerfile.frontend').read_text()
        self.assertIn('frontend/recipes-page.tsx ./frontend/src/app/workspace/recipes/page.tsx', docker)
        self.assertIn('frontend/use-chat-mode.ts ./frontend/src/components/workspace/chats/use-chat-mode.ts', docker)
        hook = (ROOT / 'frontend/use-chat-mode.ts').read_text()
        self.assertNotIn('recipeStarter', hook)
        self.assertIn('/harness-journey', (ROOT / 'frontend/recipes-page.tsx').read_text())
        self.assertIn('createSkillPrompt', hook, 'the existing skill mode keeps working')
        self.assertIn('/workspace/recipes', (ROOT / 'core/frontend/src/components/workspace/workspace-nav-chat-list.tsx').read_text())


class UserRecipes(unittest.TestCase):
    """Users create, edit and duplicate recipes; administrators share them; journeys run them like built-in ones."""
    SKILLS = ['skill-harness', 'skill-workspace', 'skill-data-pipeline', 'skill-duckdb']

    def setUp(self):
        import tempfile
        from unittest.mock import patch
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        patcher = patch.object(state, 'STATE', Path(self.temp.name) / 'state'); patcher.start(); self.addCleanup(patcher.stop)

    def draft(self, **changes):
        value = {'title': 'Dashboard demo', 'summary': 'Una dashboard semplice con dati di esempio.', 'when': 'Serve mostrare un\'idea in fretta.',
                 'attach_required': ['Un elenco degli indicatori'], 'outputs': ['Dashboard HTML con i sorgenti'],
                 'phases': [{'title': 'Indicatori', 'detail': 'Concordare misure e dimensioni', 'checkpoint': True},
                            {'title': 'Dati di esempio', 'detail': 'Generare dati coerenti', 'checkpoint': False},
                            {'title': 'Dashboard', 'detail': 'Report consultabile', 'checkpoint': True}],
                 'skills': ['skill-duckdb'], 'environment': 'dati', 'guidance': 'Usa solo dati sintetici.'}
        value.update(changes)
        return value

    def test_create_edit_visibility_and_sharing(self):
        mine = recipes.create('alice', self.draft(), self.SKILLS)
        self.assertNotIn(mine['id'], [r['id'] for r in recipes.catalog('it', 'bob')], 'private until an administrator shares it')
        card = recipes.detail(mine['id'], 'it', 'alice')
        self.assertTrue(card['custom'] and card['mine'] and not card['shared'])
        self.assertEqual(card['tools'], ['duckdb', 'jupyter', 'quarto', 'gridcraft'], 'environment tools when none are chosen')
        self.assertEqual(card['intake'], ['notes'])
        self.assertEqual([s['gate'] for s in mine['workflow']['stages']], [True, False, True])
        self.assertEqual(mine['workflow']['stages'][2]['depends_on'], ['phase-2'])
        with self.assertRaises(ValueError):
            recipes.update('bob', mine['id'], self.draft(title='Altro'), self.SKILLS, mine['revision'])
        with self.assertRaises(ValueError):
            recipes.update('alice', mine['id'], self.draft(title='Altro'), self.SKILLS, mine['revision'] - 1)
        edited = recipes.update('alice', mine['id'], self.draft(title='Dashboard vendite'), self.SKILLS, mine['revision'])
        self.assertEqual((edited['id'], edited['it']['title']), (mine['id'], 'Dashboard vendite'))
        with self.assertRaises(ValueError):
            recipes.share('alice', mine['id'], True, administrator=False)
        recipes.share('admin', mine['id'], True, administrator=True)
        self.assertIn(mine['id'], [r['id'] for r in recipes.coordinator_index(set(self.SKILLS), 'bob')])
        self.assertNotIn(mine['id'], [r['id'] for r in recipes.coordinator_index({'skill-harness'}, 'bob')], 'needs every recipe skill')
        with self.assertRaises(ValueError):
            recipes.delete('bob', mine['id'])
        recipes.delete('alice', mine['id'])
        self.assertEqual([r['id'] for r in recipes.catalog('it', 'alice')], ['data-pipeline'])

    def test_rejects_unauthorized_skills_credentials_and_unknown_tools(self):
        for changes in ({'skills': ['skill-non-abilitata']}, {'skills': []}, {'environment': 'inesistente'},
                        {'tools': ['programma-inesistente'], 'environment': None}, {'phases': []},
                        {'guidance': 'password=Segreta.2026'}, {'outputs': []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                recipes.create('alice', self.draft(**changes), self.SKILLS)

    def test_duplicate_built_in_and_run_it_as_a_guided_project(self):
        from righaven import journeys
        copy_draft = recipes.draft('data-pipeline', 'it')
        self.assertEqual(copy_draft['based_on'], 'data-pipeline')
        self.assertEqual(len(copy_draft['phases']), 7)
        copy_draft['phases'] = [p for p in copy_draft['phases'] if p['title'] in ('Comprensione e catalogo', 'Reportistica')]
        mine = recipes.create('alice', copy_draft, self.SKILLS)
        self.assertEqual(mine['skills'], ['skill-data-pipeline'])
        work = Path(self.temp.name) / 'work'; work.mkdir()
        with self.assertRaises(ValueError):
            journeys.definition(mine['id'], 'bob')
        value = journeys.start(work, mine['id'], {'goal': 'Dashboard semplice'}, 0, journeys.definition(mine['id'], 'alice'))
        self.assertEqual([s['id'] for s in value['stages']], ['phase-1', 'phase-2'])
        self.assertEqual(value['recipe']['skills'], ['skill-data-pipeline'])
        self.assertIn('DuckDB simulation', journeys.instructions(work), 'duplicated guidance travels with the copy')
        self.assertEqual(journeys.pin_policy({'sheets': [], 'hash': ''}, value), {'sheets': [], 'hash': ''})


if __name__ == '__main__':
    unittest.main()
