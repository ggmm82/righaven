"""Feedback must become actionable work, with honest before/after evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from righaven.deliveries import read_review
from righaven.control_memory import reply
from righaven.source_packages import digest
from righaven import projects


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = self.root / 'before.txt'; self.before.write_text('10')
        self.after = self.root / 'after.txt'; self.after.write_text('20')
        self.out = self.root / 'review'; self.out.mkdir()
        self.report = self.out / 'quality-review.json'

    def review(self, changes=None, engine='codex'):
        data = {'product_path': str(self.after), 'criteria': [{'requirement_id': 'total', 'criterion': 'Total 20',
            'method': 'functional', 'status': 'failed', 'evidence': 'Constraint not satisfied'}],
            'revision_actions': [{'requirement_id': 'total', 'action': 'Fix the aggregation while preserving source inputs',
                'reason': 'A value was omitted', 'priority': 1, 'strategy': 'revise'}]}
        data.update(changes or {})
        self.report.write_text(json.dumps(data))
        return read_review({'source_files': [str(self.before), str(self.after)], 'output_files': [str(self.report)]}, self.out, self.root, engine)

    def test_failed_review_keeps_action_and_instruction_in_coordinator_reply(self):
        review = self.review()
        self.assertEqual(review['status'], 'needs_revision')
        compact = json.loads(reply(self.root, {'ok': True, 'quality_review': review, 'outputs': []}, 'delegate'))
        self.assertEqual(compact['decision'], 'needs_revision')
        self.assertEqual(compact['next_action'], 'Fix the aggregation while preserving source inputs')
        self.assertIn('incarico mirato', compact['revision_instruction'])
        self.assertEqual(compact['quality_review']['revision_actions'][0]['requirement_id'], 'total')

    def test_legacy_action_plan_is_not_lost(self):
        review = self.review({'revision_actions': None, 'targeted_corrections': [
            {'priority': 1, 'panel': 'legacy free context', 'action': 'Correct the observed defect'}]})
        self.assertEqual(review['revision_actions'][0]['action'], 'Correct the observed defect')

    def test_review_feedback_survives_project_reload_and_plan_projection(self):
        review = self.review()
        projects.create_plan(self.root, 'Correct total', [])
        projects.execute_step(self.root, 'workspace', 'Produce result', '',
            lambda task, started: json.dumps({'ok': True, 'verified_products': [str(self.after)],
                'handoff': {'output_files': [str(self.after)], 'checks': []}}), purpose='delivery')
        def invoke(task, started):
            return json.dumps({'ok': True, 'quality_review': review,
                'handoff': {'source_files': [str(self.after)], 'output_files': [str(self.report)], 'checks': []}})
        projects.execute_step(self.root, 'workspace', 'Independent review', '', invoke, purpose='review')
        project = projects.read_project(self.root)
        self.assertEqual(project['revision_actions'], review['revision_actions'])
        self.assertEqual(project['next_action'], review['revision_actions'][0]['action'])
        compact = json.loads(reply(self.root, {'project': project}, 'plan'))['project']
        self.assertEqual(compact['revision_actions'], review['revision_actions'])
        self.assertEqual(compact['revision_action_count'], 1)

    def test_successful_correction_binds_both_artifacts_and_keeps_history(self):
        first = self.review()
        second = self.review({'baseline_path': str(self.before), 'criteria': [{'requirement_id': 'total',
            'criterion': 'Total 20', 'method': 'functional', 'status': 'passed', 'evidence': 'Recomputed total 20'}],
            'comparison': [{'requirement_id': 'total', 'status': 'improved', 'evidence': 'Changed from 10 to 20 by independent computation'}],
            'revision_actions': []})
        self.assertEqual(first['status'], 'needs_revision');self.assertEqual(second['status'], 'passed')
        self.assertEqual(second['comparison']['baseline_sha256'], digest(self.before))
        self.assertEqual(second['reference_hashes'][str(self.before)], digest(self.before))
        self.assertEqual(second['comparison']['product_sha256'], digest(self.after))
        self.before.write_text('mutated input')
        self.assertNotEqual(second['reference_hashes'][str(self.before)], digest(self.before))

    def test_same_bytes_do_not_prove_improvement(self):
        self.after.write_bytes(self.before.read_bytes())
        with self.assertRaisesRegex(ValueError, 'byte identici'):
            self.review({'baseline_path': str(self.before), 'comparison': [{'requirement_id': 'total', 'status': 'improved', 'evidence': 'Claim'}]})

    def test_unobserved_visual_comparison_remains_not_verified(self):
        review = self.review({'baseline_path': str(self.before), 'criteria': [{'requirement_id': 'total',
            'criterion': 'Visible requirement', 'method': 'visual', 'status': 'passed', 'evidence': 'Claim'}],
            'comparison': [{'requirement_id': 'total', 'status': 'improved', 'evidence': 'Claim'}]}, engine='deepseek')
        self.assertEqual(review['status'], 'needs_review')
        self.assertEqual(review['comparison']['criteria'][0]['status'], 'not_verified')

    def test_unlinked_requirements_and_missing_baseline_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'requisito'):
            self.review({'revision_actions': [{'requirement_id': 'invented', 'action': 'Fix', 'priority': 1}]})
        with self.assertRaisesRegex(ValueError, 'baseline_path'):
            self.review({'comparison': [{'requirement_id': 'total', 'status': 'improved', 'evidence': 'Claim'}]})

    def test_empty_comparison_preserves_review_and_failure_without_inventing_progress(self):
        review=self.review({'baseline_path':str(self.before),'comparison':[]})
        self.assertEqual(review['status'],'needs_revision')
        self.assertIsNone(review['comparison'])
        self.assertIn('non verificato',review['comparison_warning'])
        self.assertTrue(review['revision_actions'])
        self.assertEqual(json.loads(self.report.read_text())['baseline_path'],str(self.before))
        review=self.review({'baseline_path':str(self.before),'criteria':[{'requirement_id':'total','criterion':'Total',
            'method':'functional','status':'passed','evidence':'Computed total'}]})
        self.assertEqual(review['status'],'needs_review')

    def test_recurring_defect_requires_distinct_products_and_resets_after_success_or_new_brief(self):
        from righaven.revision import correction_focus
        first=self.review();first.update(sha256='first',contract_hash='brief')
        second={**first,'sha256':'second','comparison':{'baseline_sha256':'first'}}
        project={'acceptance':{'hash':'brief'},'steps':[{'attempts':[
            {'validated':True,'finished_at':'1','quality_review':first},
            {'validated':True,'finished_at':'2','quality_review':first}]}]}
        self.assertFalse(correction_focus(project)[0]['reassess_role'])
        project['steps'][0]['attempts'].append({'validated':True,'finished_at':'3','quality_review':second})
        self.assertTrue(correction_focus(project)[0]['reassess_role'])
        second['criteria']=[{**c,'status':'passed'} for c in first['criteria']]
        self.assertEqual(correction_focus(project),[])
        project['acceptance']['hash']='changed'
        self.assertEqual(correction_focus(project),[])

class ReviewFindingTests(unittest.TestCase):
    def test_advice_cannot_justify_a_failed_requirement(self):
        from righaven.revision import findings
        criteria=[{'requirement_id':'layout','status':'failed'}]
        item={'requirement_id':'layout','severity':'advisory','location':'Page 1',
              'evidence':'More whitespace might be pleasant','impact':'Optional polish'}
        with self.assertRaisesRegex(ValueError,'blocking'):
            findings({'review_version':2,'findings':[item]},criteria)
        item.update(severity='blocking',evidence='Required label is clipped in the rendered output',impact='Required content cannot be read')
        self.assertEqual(findings({'review_version':2,'findings':[item]},criteria)[0]['severity'],'blocking')
        with self.assertRaisesRegex(ValueError, 'approvato'):
            findings({'review_version':2,'findings':[item]},[{'requirement_id':'layout','status':'passed'}])
        self.assertEqual(findings({},criteria),[])  # Existing reports stay readable.

    def test_optional_advice_does_not_change_a_passing_verdict(self):
        from righaven.revision import findings
        criteria=[{'requirement_id':'layout','status':'passed'}]
        result=findings({'review_version':2,'findings':[{'severity':'advisory','location':'Cover',
            'evidence':'An alternative color is possible','impact':'Personal preference, no missing requirement'}]},criteria)
        self.assertEqual(criteria[0]['status'],'passed')
        self.assertEqual(result[0]['severity'],'advisory')
        with self.assertRaises(ValueError):findings({'review_version':2,'findings':[{'severity':'blocking'}]},criteria)
