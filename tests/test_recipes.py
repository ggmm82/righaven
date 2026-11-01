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
            self.assertTrue(card['starter'].startswith(phrase), locale)
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
        self.assertIn('Modello e catalogo', row['checkpoints'])
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
        self.assertIn('/api/harness/recipes/', hook)
        self.assertIn('createSkillPrompt', hook, 'the existing skill mode keeps working')
        self.assertIn('/workspace/recipes', (ROOT / 'core/frontend/src/components/workspace/workspace-nav-chat-list.tsx').read_text())


if __name__ == '__main__':
    unittest.main()
