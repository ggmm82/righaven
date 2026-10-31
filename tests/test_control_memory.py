"""Large production handoffs must retain actionable failures below synopsis limits."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from righaven.control_memory import LIMIT, reply
from righaven.project_skills import read_document
from righaven.project_brief import orientation


class ControlMemoryTests(unittest.TestCase):
    def test_paused_draft_is_presented_with_its_own_sources_without_claiming_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            product = '/mnt/user-data/outputs/current/sample.pdf'
            project = {'status': 'blocked', 'quality_status': 'needs_revision', 'product_path': product,
                'results': [{'path': product, 'role': 'export', 'delivery_id': 'current'},
                    {'path': '/mnt/user-data/outputs/current/sources.zip', 'role': 'source_archive', 'delivery_id': 'current'},
                    {'path': '/mnt/user-data/outputs/old/sources.zip', 'role': 'source_archive', 'delivery_id': 'old'}]}
            value = json.loads(reply(Path(temp), {'project': project}, 'plan'))['project']
            self.assertEqual(value['presentation']['paths'], [product, '/mnt/user-data/outputs/current/sources.zip'])
            self.assertIn('present_files', value['presentation']['instruction'])
            self.assertIn('incompleto', value['presentation']['instruction'])
            self.assertEqual(value['quality_status'], 'needs_revision')

    def test_large_inventory_preserves_failed_verdict_and_full_opening_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = {'ok': True, 'output_dir': '/mnt/user-data/outputs/workspace/job',
                'outputs': [{'path': f'/mnt/user-data/outputs/workspace/job/file-{i}.txt', 'role': 'editable_source',
                    'format': 'text', 'open_with': 'Real evidence ' * 100, 'reopen': {'status': 'passed', 'evidence': 'Details ' * 100}} for i in range(20)],
                'checks': [{'name': 'Constraint mismatch', 'status': 'failed', 'evidence': 'The submitted product violates an input constraint.'}],
                'delivery': {'technical_status': 'passed', 'issues': []},
                'quality_review': {'status': 'needs_revision', 'product_path': '/mnt/user-data/outputs/workspace/job/product.pdf',
                    'criteria': [{'requirement_id': 'real_constraint', 'status': 'failed', 'method': 'content', 'evidence': 'Concrete defect ' * 100}]}}
            original = copy.deepcopy(output)
            compact = reply(root, output, 'delegate'); value = json.loads(compact)
            self.assertLessEqual(len(compact), LIMIT)
            self.assertTrue(value['ok'])  # Execution succeeded, product did not pass.
            self.assertEqual(value['decision'], 'needs_revision')
            self.assertEqual(value['check_counts']['failed'], 1)
            self.assertEqual(value['review_counts']['failed'], 1)
            self.assertIn('real_constraint', compact)
            full = json.loads(read_document(root, {'path': value['details_path'], 'sha256': value['details_sha256']}))
            self.assertEqual(full, original)
            self.assertEqual(output, original)

    def test_unchecked_quality_is_never_approved_and_quota_still_blocks_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            p = reply(Path(temp), {'ok': True, 'outputs': [{'path': '/mnt/user-data/a.txt'}],
                 'checks': [{'status': 'not_run'}]}, 'delegate')
            self.assertEqual(json.loads(p)['decision'], 'review_required')
            p = json.loads(reply(Path(temp), {'ok': False, 'retry_blocked': True,
                 'attention': {'code': 'provider_quota'}, 'error': 'Quota exceeded'}, 'delegate'))
            self.assertEqual(p['decision'], 'execution_failed')
            self.assertTrue(p['retry_blocked'])
            self.assertEqual(p['attention']['code'], 'provider_quota')

    def test_plan_memory_is_bounded_without_erasing_the_original_request(self):
        with tempfile.TemporaryDirectory() as temp:
            project = {'id': 'fixture', 'brief': 'Long brief ' * 300, 'status': 'working',
                'acceptance': {'user_requests': ['Ending constraint ' * 1000], 'request_manifest': {'path': '/mnt/user-data/requests.json'},
                              'criteria': [{'id': 'r', 'requirement': 'Actual requirement', 'method': 'content', 'critical': True}]},
                'roles': [{'id': str(i), 'title': 'Dynamic role', 'mission': 'Specific mission ' * 100,
                           'tools': [], 'procedure': ['Detailed method ' * 100]} for i in range(24)], 'steps': [], 'results': [], 'deliveries': []}
            text = reply(Path(temp), {'project': project}, 'plan'); value = json.loads(text)
            self.assertLessEqual(len(text), LIMIT)
            full = json.loads(read_document(Path(temp), {'path': value['details_path'], 'sha256': value['details_sha256']}))
            self.assertEqual(full['project']['acceptance']['user_requests'], project['acceptance']['user_requests'])
            # Over the limit, an ordinary plan update need not be re-read; a reported problem must be.
            from unittest.mock import patch
            from righaven import control_memory
            with patch.object(control_memory, 'LIMIT', 900):
                ordinary = json.loads(reply(Path(temp), {'project': project}, 'plan'))
                project['attention'] = {'code': 'provider_quota', 'message': 'Quota esaurita'}
                problem = json.loads(reply(Path(temp), {'project': project}, 'plan'))
            self.assertIs(ordinary['details_required'], False)
            self.assertIs(problem['details_required'], True)
            self.assertIn('details_path', ordinary)

    def test_phase_projection_preserves_history_and_live_retired_role(self):
        steps = [{'id': 'old', 'role_id': 'retired', 'status': 'pending', 'goal': 'Old plan', 'attempts': []},
                 {'id': 'live', 'role_id': 'retired', 'status': 'running', 'goal': 'Worker finishing', 'attempts': []},
                 {'id': 'new', 'role_id': 'current', 'status': 'pending', 'goal': 'Next result', 'attempts': []}]
        value = {'steps': steps, 'roles': [{'id': 'current'}]}
        view = orientation(value)
        self.assertEqual(view['active_step_ids'], ['live', 'new'])
        self.assertEqual(view['history_step_ids'], ['old'])
        self.assertEqual(view['counts']['pending'], 1)
        self.assertEqual(len(value['steps']), 3)
        value['roles'].append({'id': 'retired'})
        self.assertEqual(orientation(value)['active_step_ids'], ['old', 'live', 'new'])

    def test_worst_case_reply_and_secrets_remain_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            result = {'ok': True, 'checks': [{'name': 'failed ' * 100, 'status': 'failed', 'evidence': 'x' * 1000}] * 100,
                      'outputs': [{'path': '/mnt/user-data/' + 'x' * 1000}] * 100,
                      'delivery': {'technical_status': 'needs_revision', 'issues': ['x' * 1000] * 100}, 'token': 'private'}
            text = reply(Path(temp), result, 'delegate')
            self.assertLessEqual(len(text), LIMIT)
            self.assertNotIn('private', text)
            self.assertEqual(json.loads(text)['decision'], 'needs_revision')

    def test_mixed_subchecks_have_one_failed_verdict_instead_of_cherry_picking_passed(self):
        with tempfile.TemporaryDirectory() as temp:
            criteria=[{'requirement_id':'quality','status':'passed','evidence':'Local aspect works'},
                      {'requirement_id':'quality','status':'failed','evidence':'Critical defect persists'}]
            result={'ok':True,'quality_review':{'status':'needs_revision','criteria':criteria}}
            value=json.loads(reply(Path(temp),result,'delegate'))
            verdict=value['quality_review']['requirement_verdicts'][0]
            self.assertEqual(verdict['status'],'failed')
            self.assertEqual(verdict['observations'],2)
            self.assertEqual(value['decision'],'needs_revision')
            self.assertIn('campione',value['review_scope_instruction'])
            self.assertNotIn('requirement_verdicts',result['quality_review'])
