"""A recorded assignment is never reported as failed nor silently run twice."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import projects, state


class DuplicateAssignmentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'conversation'; self.root.mkdir()
        fixture = patch.object(state, 'STATE', Path(temp.name) / 'state'); fixture.start(); self.addCleanup(fixture.stop)
        projects.create_plan(self.root, 'Documento', [{'id': 'draft', 'agent': 'workspace', 'goal': 'Bozza'}],
                             outcome={'result': 'Documento', 'format': 'Markdown'})
        projects.set_checkpoints(self.root, False)
        self.runs = 0

    def execute(self, task='Scrivi la bozza', turn='turn-1', purpose='work'):
        def invoke(instructions, started):
            self.runs += 1
            folder = self.root / 'outputs' / ('job' + str(self.runs)); folder.mkdir(parents=True)
            (folder / 'out.md').write_text('testo')
            return json.dumps({'ok': True, 'output_dir': str(folder), 'handoff': {'source_files': [], 'previews': [],
                'output_files': [str(folder / 'out.md')], 'checks': [{'name': 'Letto', 'status': 'passed', 'evidence': 'riaperto'}]}})
        return json.loads(projects.execute_step(self.root, 'workspace', task, 'draft', invoke, purpose=purpose, request_id=turn))

    def test_the_same_assignment_in_the_same_turn_returns_the_recorded_result(self):
        first = self.execute()
        again = self.execute()
        self.assertEqual(self.runs, 1)
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['output_dir'], first['output_dir'])
        # A different task, purpose or user turn is new work.
        self.execute(task='Rivedi la bozza'); self.execute(purpose='preview'); self.execute(turn='turn-2')
        self.assertEqual(self.runs, 4)


try:
    from righaven.tools import harness_delegate
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    harness_delegate = None


@unittest.skipIf(harness_delegate is None, 'Requires the pinned Gateway tool runtime')
class RecordedResultTests(unittest.TestCase):
    def test_a_failing_summary_after_completion_is_not_reported_as_a_failed_assignment(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory, patch.object(state, 'STATE', Path(directory) / 'state'):
            root = Path(directory) / 'conversation'; root.mkdir()
            projects.create_plan(root, 'Documento', [{'id': 'draft', 'agent': 'wordcraft', 'goal': 'Bozza'}],
                                 outcome={'result': 'Documento', 'format': 'Markdown'})
            folder = root / 'outputs' / 'job'; folder.mkdir(parents=True); (folder / 'out.md').write_text('testo')
            reply = {'ok': True, 'output_dir': str(folder), 'available_files': [str(folder / 'out.md')],
                     'handoff': {'source_files': [], 'previews': [], 'output_files': [str(folder / 'out.md')],
                                 'checks': [{'name': 'Letto', 'status': 'passed', 'evidence': 'riaperto'}]}}
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='turn-1', content='Scrivi un documento')]})
            from righaven.capability_policy import policy_from_names
            capabilities = policy_from_names({'skill-' + a['id'] for a in state.applications()}, source='fixture')
            with patch('righaven.tools.workspace_for', return_value=root), \
                 patch('righaven.capability_policy.runtime_policy', return_value=capabilities), \
                 patch('righaven.tools.experience_root', return_value=Path(directory) / 'library'), \
                 patch('righaven.state.team', return_value={'engine': 'deepseek', 'model': 'fixture'}), \
                 patch('righaven.tools.delegate', return_value=json.dumps(reply)), \
                 patch('righaven.tools.delegation_reply', side_effect=RuntimeError('summary broke')):
                result = json.loads(harness_delegate.func(agent='wordcraft', task='Scrivi', step_id='draft', runtime=runtime))
            self.assertTrue(result['ok'])
            self.assertTrue(result['summary_unavailable'])
            self.assertIn('non rilanciarlo', result['instruction'])
            self.assertEqual(projects.read_project(root)['steps'][0]['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
