"""A failed production method is not proof that the user owes us missing assets."""
import json
from pathlib import Path
import tempfile
import unittest

from righaven import projects
from righaven.acceptance import contract, evaluate
from righaven.project_skills import read_document
from righaven.control_memory import reply


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proof = self.root / 'review.json'; self.proof.write_text('{"defect":"observed"}')
        projects.create_plan(self.root, 'Requested result', [], outcome={'result': 'Complete requested product',
            'format': 'Editable deliverable', 'constraints': ['Preserve source content'], 'assumptions': ['Team-chosen method A']})
        projects.sync_acceptance(self.root, ['Preserve the content; choose the method yourself.'])
        projects.execute_step(self.root, 'workspace', 'Review sample', 'review', lambda task, started:
            json.dumps({'ok': True, 'quality_review': {'status': 'needs_revision', 'product_path': str(self.proof)},
                        'handoff': {'output_files': [str(self.proof)], 'checks': []}}), purpose='review')

    def strategy(self, **changes):
        value = {'method': 'Original method', 'reason': 'Sample failed; another method must be considered',
                 'state': 'exploring', 'alternatives': [{'method': 'Alternative construction', 'reason': 'Addresses observed defect',
                    'status': 'candidate', 'tools': ['vectorcraft']}]}
        value.update(changes); return value

    def test_failed_sample_without_method_decision_does_not_become_external_blocker(self):
        p = projects.create_plan(self.root, '', [], status='blocked', summary='Need external assets')
        self.assertEqual(p['status'], 'review')
        self.assertEqual(p['method_recovery']['code'], 'method_selection_required')
        self.assertIn('outcome.assumptions', p['method_recovery']['instruction'])
        compact = json.loads(reply(self.root, {'project': p}, 'plan'))['project']
        self.assertIn('method_recovery', compact)
        self.assertTrue(self.proof.exists())

    def test_successful_execution_with_failed_sample_checks_keeps_files_and_requires_revision(self):
        response = json.loads(projects.execute_step(self.root, 'workspace', 'Try alternate method', 'sample',
            lambda task, started: json.dumps({'ok': True, 'handoff': {
                'output_files': [str(self.proof)], 'checks': [
                    {'name': 'Representative result quality', 'status': 'failed'},
                    {'name': 'Native reopen', 'status': 'passed'}]}})))
        self.assertTrue(response['ok'])  # Execution succeeded; product did not.
        self.assertEqual(response['activity']['status'], 'needs_revision')
        self.assertEqual(response['method_recovery']['code'], 'method_selection_required')
        project = projects.read_project(self.root)
        self.assertIn('correzioni', project['summary'])
        self.assertTrue(self.proof.exists())

    def test_untried_alternative_prevents_capability_block_but_budget_choice_is_allowed(self):
        s = self.strategy(state='needs_user', stop_reason='capability_limit', user_action='Supply assets')
        p = projects.create_plan(self.root, '', [], strategy=s, status='blocked')
        self.assertEqual(p['status'], 'review')
        s.update(stop_reason='budget', user_action='Choose whether to fund another sample')
        p = projects.create_plan(self.root, '', [], strategy=s, status='blocked')
        self.assertEqual(p['status'], 'blocked')
        self.assertEqual(p['next_action'], s['user_action'])

    def test_honest_dependency_decision_requires_evidence_and_keeps_versioned_method(self):
        s = self.strategy(state='needs_user', stop_reason='missing_input', user_action='Provide the requested reference')
        s['alternatives'][0].update(status='tested', evidence_paths=['/mnt/user-data/review.json'])
        p = projects.create_plan(self.root, '', [], strategy=s, status='blocked')
        self.assertEqual(p['status'], 'blocked')
        record = p['strategy']['record']
        self.assertIn('reference', read_document(self.root, record))
        self.proof.write_text('Changed after review')
        p = projects.create_plan(self.root, '', [], status='blocked')
        self.assertEqual(p['status'], 'review')
        self.assertIn('reference', read_document(self.root, record))  # History remains intact.

    def test_claimed_trials_and_unknown_tools_are_rejected(self):
        for change in ({'status': 'tested'}, {'tools': ['invented-generator']},
                       {'status': 'tested', 'evidence_paths': ['/etc/passwd']}):
            s = self.strategy(); s['alternatives'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                projects.create_plan(self.root, '', [], strategy=s)

    def test_real_operational_pause_and_explicit_idle_do_not_trigger_method_work(self):
        projects.execute_step(self.root, 'workspace', 'Work', 'outage', lambda task, started:
            json.dumps({'ok': False, 'error': 'quota exceeded'}))
        self.assertEqual(projects.create_plan(self.root, '', [], status='blocked')['status'], 'blocked')
        self.assertEqual(projects.create_plan(self.root, '', [], status='idle')['status'], 'idle')

    def test_workers_receive_revisable_assumptions_and_strategy_across_domains(self):
        for domain in ('book', 'building', 'software', 'event'):
            s = self.strategy(method='Method for ' + domain, state='selected')
            projects.create_plan(self.root, '', [], strategy=s, status='working')
            captured = []
            projects.execute_step(self.root, 'workspace', 'Produce ' + domain, '', lambda task, started:
                captured.append(task) or json.dumps({'ok': True}))
            self.assertIn('Non trasformarle in requisiti dell’utente', captured[0])
            self.assertIn('Team-chosen method A', captured[0])
            self.assertIn('.righaven-project/strategies/', captured[0])

    def test_user_provenance_cannot_be_invented_or_promote_proposal_to_automatic_pass(self):
        c = {'id': 'style', 'requirement': 'Team style', 'method': 'visual', 'origin': 'user', 'source_quote': 'User demands realism'}
        with self.assertRaisesRegex(ValueError, 'messaggi reali'):
            contract(['Choose a suitable style'], [c])
        c.update(origin='proposal', source_quote='')
        a = contract(['Choose a suitable style'], [c])
        _, status = evaluate([{'requirement_id': 'style', 'method': 'visual', 'status': 'failed'}], a, 'codex')
        self.assertEqual(status, 'needs_revision')

    def test_old_user_quote_survives_compaction_and_new_brief_invalidates_stop_decision(self):
        projects.sync_acceptance(self.root, ['Must keep editable source files'])
        c = {'id': 'sources', 'requirement': 'Editable source files', 'method': 'structural', 'origin': 'user',
             'source_quote': 'Must keep editable source files'}
        projects.sync_acceptance(self.root, ['Another input'], [c])
        for i in range(10): projects.sync_acceptance(self.root, ['Clarification ' + str(i)])
        self.assertEqual(projects.read_project(self.root)['acceptance']['criteria'][1]['origin'], 'user')
        s = self.strategy(state='needs_user', stop_reason='user_choice', user_action='Choose the next approach')
        projects.create_plan(self.root, '', [], strategy=s, status='blocked')
        projects.sync_acceptance(self.root, ['Proceed with the supplied reference'])
        self.assertEqual(projects.create_plan(self.root, '', [], status='blocked')['status'], 'review')
