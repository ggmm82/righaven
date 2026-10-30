"""Tool alternatives in the brief: the team recommends, only the user chooses."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import projects, state
from righaven.project_brief import briefing_issue, rejected_tools, validate_outcome


def decision(chosen=''):
    return {'id': 'pdf', 'decision': 'Impaginazione del PDF', 'recommended': 'typst',
            'recommendation_reason': 'Sorgente leggibile e compilazione riproducibile',
            'options': [{'id': 'typst', 'label': 'Typst', 'tools': ['typst'], 'pros': ['Veloce'], 'cons': ['Meno diffuso']},
                        {'id': 'pandoc', 'label': 'Pandoc', 'tools': ['pandoc'], 'pros': ['Molti formati'], 'cons': ['Controllo tipografico limitato']}],
            'chosen': chosen}


def outcome(chosen=''):
    return {'result': 'Brochure', 'format': 'PDF', 'tool_options': [decision(chosen)]}


class ToolChoiceTests(unittest.TestCase):
    def test_alternatives_need_pros_cons_and_a_motivated_recommendation(self):
        self.assertEqual(validate_outcome(outcome())['tool_options'][0]['recommended'], 'typst')
        broken = decision(); broken['options'] = broken['options'][:1]
        with self.assertRaisesRegex(ValueError, 'da due a quattro'):
            validate_outcome({**outcome(), 'tool_options': [broken]})
        broken = decision(); broken['options'][1]['cons'] = []
        with self.assertRaisesRegex(ValueError, 'pregio e un difetto'):
            validate_outcome({**outcome(), 'tool_options': [broken]})
        with self.assertRaisesRegex(ValueError, 'consiglia'):
            validate_outcome({**outcome(), 'tool_options': [{**decision(), 'recommended': 'unknown'}]})
        broken = decision(); broken['options'][0]['tools'] = ['not-a-tool']
        with self.assertRaisesRegex(ValueError, 'catalogo'):
            validate_outcome({**outcome(), 'tool_options': [broken]})

    def test_production_waits_for_the_choice_and_rejected_programs_are_excluded(self):
        self.assertIn('Impaginazione del PDF', briefing_issue(validate_outcome(outcome())))
        chosen = validate_outcome(outcome('pandoc'))
        self.assertIsNone(briefing_issue(chosen))
        self.assertEqual(rejected_tools(chosen), {'typst'})

    def test_the_choice_is_recorded_only_after_a_new_user_turn(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(state, 'STATE', Path(directory) / 'state'):
            root = Path(directory) / 'conversation'; root.mkdir()
            projects.create_plan(root, 'Brochure', [], outcome=outcome(), source_turn='turn-1')
            self.assertEqual(projects.read_project(root)['status'], 'clarifying')
            with self.assertRaisesRegex(ValueError, 'spetta all’utente'):
                projects.create_plan(root, '', [], outcome=outcome('typst'), source_turn='turn-1')
            with self.assertRaisesRegex(ValueError, 'spetta all’utente'):
                projects.create_plan(root, 'Altro', [], outcome={**outcome('typst'), 'tool_options': [{**decision('typst'), 'id': 'new'}]},
                                     source_turn='turn-2')  # never presented before
            projects.create_plan(root, '', [], outcome=outcome('pandoc'), source_turn='turn-2')
            self.assertEqual(projects.read_project(root)['outcome']['tool_options'][0]['chosen'], 'pandoc')


try:
    from righaven.tools import harness_plan
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    harness_plan = None


@unittest.skipIf(harness_plan is None, 'Requires the pinned Gateway tool runtime')
class ToolChoiceRoleTests(unittest.TestCase):
    def test_roles_cannot_use_programs_of_rejected_alternatives(self):
        from types import SimpleNamespace
        from test_project_skills import role
        from righaven.capability_policy import policy_from_names
        capabilities = policy_from_names({'skill-' + a['id'] for a in state.applications()}, source='fixture')
        with tempfile.TemporaryDirectory() as directory, patch.object(state, 'STATE', Path(directory) / 'state'), \
                patch('righaven.tools.workspace_for', return_value=Path(directory)), \
                patch('righaven.tools.experience_root', return_value=Path(directory) / 'library'), \
                patch('righaven.capability_policy.runtime_policy', return_value=capabilities):
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='turn-1', content='Una brochure PDF')]})
            harness_plan.func(runtime=runtime, brief='Brochure', outcome_json=json.dumps(outcome()))
            runtime.state['messages'].append(SimpleNamespace(type='human', id='turn-2', content='Preferisco pandoc'))
            harness_plan.func(runtime=runtime, outcome_json=json.dumps(outcome('pandoc')))
            with self.assertRaisesRegex(ValueError, 'alternative non scelte'):
                harness_plan.func(runtime=runtime, roles_json=json.dumps([{**role(), 'tools': ['typst']}]))
            harness_plan.func(runtime=runtime, roles_json=json.dumps([{**role(), 'tools': ['pandoc']}]))


if __name__ == '__main__':
    unittest.main()
