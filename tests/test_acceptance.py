"""Generic request fidelity and review policy, independent of file format/CLI."""
import json
from pathlib import Path
import tempfile
import unittest

from righaven.acceptance import contract, evaluate
from righaven.deliveries import read_review
from righaven import projects


class AcceptanceTests(unittest.TestCase):
    def test_file_validity_does_not_prove_the_requested_content(self):
        expected = contract(['Produce the requested result'])
        values, status = evaluate([{'criterion': 'File opens', 'method': 'technical',
            'requirement_id': 'request_fidelity', 'status': 'passed', 'evidence': 'Valid header'}], expected, 'codex')
        self.assertEqual(status, 'needs_review')
        self.assertEqual(values[0]['status'], 'not_run')
        _, status = evaluate([{'criterion': 'Good', 'method': 'content', 'status': 'passed', 'evidence': 'Good'}], expected, 'codex')
        self.assertEqual(status, 'needs_review')  # Named requirements must be covered.

    def test_unavailable_observation_is_not_a_success_for_any_product(self):
        for engine, method in [('deepseek', 'visual'), ('deepseek', 'listening'), ('codex', 'listening'), ('gemini', 'listening')]:
            with self.subTest(engine=engine, method=method):
                _, status = evaluate([{'criterion': 'Perceptual quality', 'method': method,
                    'status': 'passed', 'evidence': 'I generated a preview'}], None, engine)
                self.assertEqual(status, 'needs_review')

    def test_missing_reference_and_wrong_verification_method_cannot_pass(self):
        expected = contract(['Follow my reference'], [{'id': 'reference', 'requirement': 'Match the reference',
            'method': 'reference', 'reference_paths': []}])
        checks = [{'requirement_id': 'request_fidelity', 'criterion': 'Request', 'method': 'content', 'status': 'passed', 'evidence': 'Compared content'},
                  {'requirement_id': 'reference', 'criterion': 'Reference', 'method': 'technical', 'status': 'passed', 'evidence': 'File is valid'}]
        _, status = evaluate(checks, expected, 'codex')
        self.assertEqual(status, 'needs_review')
        checks[1]['method'] = 'reference'
        _, status = evaluate(checks, expected, 'codex')
        self.assertEqual(status, 'needs_review')

    def test_original_request_is_not_overwritten_by_coordinator_or_context_compaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects.create_plan(root, 'Coordinator interpretation', [])
            projects.sync_acceptance(root, ['Original request', 'Make it red'])
            projects.create_plan(root, 'An easier alternative', [])
            projects.sync_acceptance(root, ['Add a title'])
            saved = projects.read_project(root)['acceptance']
            self.assertEqual(saved['user_requests'], ['Original request', 'Make it red', 'Add a title'])
            projects.sync_acceptance(root, ['Original request', 'Make it red', 'Add a title'])
            self.assertEqual(projects.read_project(root)['acceptance']['hash'], saved['hash'])

    def test_reference_proof_requires_the_actual_input_and_records_its_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product, reference = root / 'product.txt', root / 'reference.txt'
            product.write_text('Observed output');reference.write_text('Required reference')
            out = root / 'review';out.mkdir()
            report = out / 'quality-review.json'
            value = {'product_path': str(product), 'criteria': [
                {'requirement_id': 'request_fidelity', 'criterion': 'Faithful', 'method': 'content', 'status': 'passed', 'evidence': 'Observed content'},
                {'requirement_id': 'match', 'criterion': 'Matches actual reference', 'method': 'reference', 'status': 'passed', 'evidence': 'Compared actual data'}]}
            report.write_text(json.dumps(value))
            expected = contract(['Match reference'], [{'id': 'match', 'requirement': 'Match supplied data', 'method': 'reference', 'reference_paths': [str(reference)]}])
            handoff = {'output_files': [str(report)], 'source_files': [str(product)]}
            self.assertEqual(read_review(handoff, out, root, 'codex', expected)['status'], 'needs_review')
            handoff['source_files'].append(str(reference))
            reviewed = read_review(handoff, out, root, 'codex', expected)
            self.assertEqual(reviewed['status'], 'passed')
            self.assertEqual(reviewed['reference_hashes'][str(reference)], projects.digest(reference))

    def test_same_generic_policy_and_same_step_review_work_for_all_catalog_tools(self):
        for app in projects.applications():
            with self.subTest(tool=app['id']), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                projects.create_plan(root, 'Coordinator plan', [])
                projects.sync_acceptance(root, ['Preserve the content I requested'])
                folder = root / 'outputs' / app['id'] / 'production'; folder.mkdir(parents=True)
                product, source = folder / 'result.txt', folder / 'source.txt'
                product.write_text('Declared fixture: orchestration only');source.write_text('Editable fixture')
                handoff = {'source_files': [], 'output_files': [str(product), str(source)], 'checks': []}
                record = {'id': 'production', 'technical_status': 'passed', 'files': [
                    {'path': str(p), 'sha256': projects.digest(p), 'role': 'export' if p == product else 'editable_source'} for p in [product, source]]}
                reply = {'ok': True, 'output_dir': str(folder), 'handoff': handoff, 'delivery_record': record}
                projects.execute_step(root, app['id'], 'Produce fixture', 'shared', lambda *args: json.dumps(reply), purpose='delivery')
                acceptance = projects.read_project(root)['acceptance']
                review_folder = root / 'outputs' / app['id'] / 'review';review_folder.mkdir()
                report = review_folder / 'quality-review.json'
                report.write_text(json.dumps({'product_path': str(product), 'criteria': [{
                    'requirement_id': 'request_fidelity', 'criterion': 'Requested content', 'method': 'content',
                    'status': 'passed', 'evidence': 'Declared fixture observation of actual content'}]}))
                rh = {'output_files': [str(report)], 'source_files': [str(product)], 'checks': []}
                review = read_review(rh, review_folder, root, 'codex', acceptance)
                projects.execute_step(root, app['id'], 'Review fixture', 'shared', lambda *args: json.dumps({
                    'ok': True, 'output_dir': str(review_folder), 'handoff': rh, 'quality_review': review}), purpose='review')
                state = projects.read_project(root)
                self.assertIn('/mnt/user-data/outputs/' + app['id'] + '/production/result.txt', [r['path'] for r in state['results']])
                self.assertTrue(any(d['id'] == 'production' and d['current'] for d in state['deliveries']))
                self.assertEqual(projects.create_plan(root, '', [], status='ready')['status'], 'ready')
                # A changed request cannot reuse an old positive review.
                projects.sync_acceptance(root, ['Preserve the content I requested', 'Use a different reference'])
                with self.assertRaisesRegex(ValueError, 'revisione separata'):
                    projects.create_plan(root, '', [], status='ready')

    def test_requirement_verdicts_keep_failures_and_unknowns_in_either_order(self):
        from righaven.acceptance import requirement_verdicts
        for states, expected in [(['passed','failed'],'failed'),(['failed','passed'],'failed'),
                                 (['passed','not_run'],'not_run'),(['passed','passed'],'passed')]:
            with self.subTest(states=states):
                verdict=requirement_verdicts([{'requirement_id':'same','status':state} for state in states])[0]
                self.assertEqual(verdict['status'],expected)
                self.assertEqual(verdict['observations'],2)


if __name__ == '__main__':
    unittest.main()
