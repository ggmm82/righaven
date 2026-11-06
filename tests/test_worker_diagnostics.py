from types import SimpleNamespace
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from righaven.run_agent import command, worker_error, handoff_error


class WorkerDiagnosticsTests(unittest.TestCase):
    def test_legacy_codex_errors_are_structured(self):
        prompt = 'Contesto privato\n' * 20000
        events = [{'type': 'item.completed', 'item': {'text': prompt}},
                  {'type': 'turn.failed', 'error': {'message': 'Model is not supported'}}]
        result = SimpleNamespace(stdout='\n'.join(map(json.dumps, events)), stderr=prompt)
        self.assertEqual(worker_error('codex', result), 'Model is not supported')

    def test_stderr_diagnostic_keeps_cause_instead_of_tail_of_prompt(self):
        result = SimpleNamespace(stdout='', stderr='Error: invalid model\n' + 'Private context\n' * 1000)
        self.assertEqual(worker_error('codex', result), 'Error: invalid model')

    def test_failed_handoff_reports_actual_cause_without_becoming_success(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'handoff.json').write_text(json.dumps({
                'output_files': [], 'checks': [
                    {'status': 'passed', 'evidence': 'discovery succeeded'},
                    {'status': 'failed', 'evidence': 'python: command not found'}]}))
            diagnostic = handoff_error(output, ValueError('output_files vuoto'))
            self.assertIn('output_files vuoto', diagnostic)
            self.assertIn('python: command not found', diagnostic)
            self.assertNotIn('discovery succeeded', diagnostic)
            (output / 'handoff.json').write_text('null')
            self.assertEqual(handoff_error(output, ValueError('invalid manifest')), 'invalid manifest')

    def test_handoff_diagnostics_do_not_follow_external_symlinks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'outputs'
            output.mkdir()
            outside = root / 'private.json'
            outside.write_text(json.dumps({'checks': [{'status': 'failed', 'evidence': 'private'}]}))
            (output / 'handoff.json').symlink_to(outside)
            self.assertEqual(handoff_error(output, ValueError('external manifest')), 'external manifest')
