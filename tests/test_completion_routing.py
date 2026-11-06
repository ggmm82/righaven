"""A limited experiment and an unavailable observation must not cause retry loops."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from righaven.acceptance import contract, evaluate
from righaven.control_memory import continuation, reply
from righaven.deliveries import read_review, build_delivery
from righaven import projects
from righaven.revision import correction_focus
from righaven.completion_policy import needs_continuation


class CompletionRoutingTests(unittest.TestCase):
    def test_incomplete_production_is_not_a_justified_terminal_state(self):
        self.assertTrue(needs_continuation({'status': 'review', 'next_action': 'Fix panel position'}))
        for project in [{'status': 'ready'}, {'status': 'review', 'user_control': {'paused': True}},
                {'status': 'blocked', 'attention': {'code': 'provider_quota'}},
                {'status': 'review', 'strategy': {'state': 'needs_user', 'stop_reason': 'Reference missing', 'user_action': 'Provide reference'}},
                {'status': 'review', 'review_criteria': [{'status': 'not_run', 'method': 'listening'}], 'review_unavailable_methods': ['listening']}]:
            with self.subTest(project=project):
                self.assertFalse(needs_continuation(project))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.product = self.root / 'outputs/production/result.txt'
        self.product.parent.mkdir(parents=True)
        self.product.write_text('Actual limited experiment')
        self.out = self.root / 'outputs/review'
        self.out.mkdir()
        self.report = self.out / 'quality-review.json'
        self.acceptance = contract(['A complete product with an observed result'], [
            {'id': 'risk', 'requirement': 'Riskiest property', 'method': 'functional'},
            {'id': 'extent', 'requirement': 'Full extent', 'method': 'technical'},
            {'id': 'perception', 'requirement': 'Perceptual quality', 'method': 'listening'}])
        self.criteria = [self.criterion('request_fidelity', 'content', 'failed'),
            self.criterion('risk', 'functional', 'passed'),
            self.criterion('extent', 'technical', 'failed'),
            self.criterion('perception', 'listening', 'not_run')]

    def criterion(self, identifier, method, status):
        return {'requirement_id': identifier, 'criterion': identifier, 'method': method,
                'status': status, 'evidence': 'Observed fixture: limited experiment, not a finished product'}

    def review(self, ids=None):
        value = {'product_path': str(self.product), 'criteria': self.criteria}
        if ids is not None:
            value['scope'] = {'kind': 'checkpoint', 'question': 'Does the method solve the selected risk?',
                              'requirement_ids': ids}
        self.report.write_text(json.dumps(value))
        return read_review({'source_files': [str(self.product)], 'output_files': [str(self.report)]},
                           self.out, self.root, 'codex', self.acceptance)

    def test_checkpoint_pass_does_not_approve_full_contract_or_erase_failures(self):
        review = self.review(['risk'])
        self.assertEqual(review['checkpoint']['status'], 'passed')
        self.assertFalse(review['checkpoint']['final_approval'])
        self.assertEqual(review['status'], 'needs_revision')
        self.assertEqual(continuation(review)['action'], 'continue_production')
        self.assertIn('extent', review['checkpoint']['remaining_requirement_ids'])
        self.assertEqual(next(c for c in review['criteria'] if c['requirement_id'] == 'extent')['status'], 'failed')
        # Persist and reload using the real project path; the final ready guard
        # must continue to reject this otherwise technically valid delivery.
        projects.create_plan(self.root, 'Product', [])
        projects.sync_acceptance(self.root, ['A complete product with an observed result'], self.acceptance['criteria'])
        current = projects.read_project(self.root)['acceptance']
        review['contract_hash'] = current['hash']
        record = {'id': 'production', 'technical_status': 'passed', 'files': [
            {'path': str(self.product), 'role': 'export', 'sha256': projects.digest(self.product)}]}
        projects.execute_step(self.root, 'workspace', 'Production', '', lambda *a: json.dumps({
            'ok': True, 'output_dir': str(self.product.parent), 'delivery_record': record,
            'handoff': {'output_files': [str(self.product)], 'checks': []}}), purpose='delivery')
        projects.execute_step(self.root, 'workspace', 'Review', '', lambda *a: json.dumps({
            'ok': True, 'quality_review': review, 'handoff': {'output_files': [str(self.report)], 'checks': []}}), purpose='review')
        state = projects.read_project(self.root)
        self.assertEqual(state['review_checkpoint']['status'], 'passed')
        self.assertIn('da completare', state['summary'])
        self.assertEqual(correction_focus(json.loads((self.root / '.righaven-project/project.json').read_text())), [])
        with self.assertRaises(ValueError):
            projects.create_plan(self.root, '', [], status='ready')

    def test_failed_checkpoint_is_targeted_correction_not_another_full_production(self):
        self.criteria[1]['status'] = 'failed'
        review = self.review(['risk'])
        self.assertEqual(continuation(review)['action'], 'revise_checkpoint')
        self.assertEqual(continuation(review)['failed_requirement_ids'], ['risk'])

    def test_unavailable_check_waits_for_user_without_inventing_approval(self):
        for c in self.criteria:
            c['status'] = 'passed'
        review = self.review()
        self.assertEqual(review['status'], 'needs_review')
        self.assertEqual(review['unavailable_methods'], ['listening'])
        routing = continuation(review)
        self.assertEqual(routing['action'], 'request_user_verification')
        self.assertIn('non rigenerare', routing['instruction'])
        # A real defect still takes precedence over a missing sensory check.
        self.criteria[1]['status'] = 'failed'
        self.assertEqual(continuation(self.review())['action'], 'revise_product')

    def test_missing_available_check_is_not_misclassified_as_human_only(self):
        self.criteria[0]['status'] = 'passed'
        self.criteria[2]['status'] = 'not_run'
        self.assertEqual(continuation(self.review())['action'], 'verify_product')

    def test_unknown_empty_or_repeated_scope_is_rejected(self):
        for ids in [[], ['unknown'], ['risk', 'risk']]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.review(ids)

    def test_explicit_final_scope_accepts_the_report_without_narrowing_acceptance(self):
        value = {'product_path': str(self.product), 'criteria': self.criteria,
                 'scope': {'kind': 'final', 'requirement_ids': ['risk']}}
        self.report.write_text(json.dumps(value))
        review = read_review({'source_files': [str(self.product)], 'output_files': [str(self.report)]},
                             self.out, self.root, 'codex', self.acceptance)
        self.assertIsNone(review['checkpoint'])
        self.assertEqual(review['status'], 'needs_revision')
        self.assertTrue(any(c['requirement_id'] == 'extent' and c['status'] == 'failed' for c in review['criteria']))
        self.criteria = [self.criterion('request_fidelity', 'content', 'passed')]
        value.update(criteria=self.criteria, scope={'kind':'final'})
        self.report.write_text(json.dumps(value))
        review = read_review({'source_files': [str(self.product)], 'output_files': [str(self.report)]},
                             self.out, self.root, 'codex', self.acceptance)
        self.assertEqual(review['status'], 'needs_review')

    def test_full_verdict_and_routing_survive_large_control_reply(self):
        review = self.review(['risk'])
        value = json.loads(reply(self.root, {'ok': True, 'quality_review': review,
            'outputs': [{'path': '/mnt/user-data/' + str(i), 'open_with': 'long text ' * 100} for i in range(50)]}, 'delegate'))
        self.assertEqual(value['decision'], 'needs_revision')
        self.assertEqual(value['quality_review']['checkpoint']['status'], 'passed')
        self.assertEqual(value['continuation']['action'], 'continue_production')

    def test_measurable_failure_is_not_erased_by_a_bundled_sensory_requirement(self):
        criteria = [self.criterion('perception', 'technical', 'failed')]
        values, status = evaluate(criteria, self.acceptance, 'codex')
        self.assertEqual(values[0]['status'], 'failed')
        self.assertEqual(status, 'needs_revision')
        criteria[0]['status'] = 'passed'
        values, _ = evaluate(criteria, self.acceptance, 'codex')
        self.assertEqual(values[0]['status'], 'not_run')

    def test_admitted_defects_route_to_focused_repair_before_another_full_review(self):
        value = json.loads(reply(self.root, {'ok': True, 'checks': [
            {'name': 'Unresolved defect', 'status': 'failed', 'evidence': 'Still visible'}]}, 'delegate'))
        self.assertEqual(value['decision'], 'needs_revision')
        self.assertEqual(value['continuation']['action'], 'repair_known_defects')

    def test_new_sample_is_discoverable_without_promoting_or_replacing_selected_product(self):
        projects.create_plan(self.root, 'Product', [])
        for number in (1, 2):
            folder = self.root / 'outputs' / ('sample' + str(number)); folder.mkdir()
            product, frame = folder / 'sample.txt', folder / 'frame.txt'
            product.write_text('Sample ' + str(number)); frame.write_text('Representative excerpt')
            record = {'id': folder.name, 'technical_status': 'needs_revision', 'files': [
                {'path': str(frame), 'role': 'preview', 'sha256': projects.digest(frame)},
                {'path': str(product), 'role': 'export', 'sha256': projects.digest(product)}]}
            projects.execute_step(self.root, 'workspace', 'Experiment', 'sample', lambda *a: json.dumps({
                'ok': True, 'output_dir': str(folder), 'delivery_record': record,
                'handoff': {'output_files': [str(frame), str(product)], 'checks': []}}), purpose='preview')
        state = projects.read_project(self.root)
        self.assertEqual(state['product_path'], '')
        self.assertEqual(state['latest_sample']['delivery_id'], 'sample2')
        self.assertEqual(state['latest_sample']['path'], '/mnt/user-data/outputs/sample2/sample.txt')
        self.assertNotEqual(state['status'], 'ready')
        self.assertTrue(any(r['delivery_id'] == 'sample1' for r in state['results']))
        compact = json.loads(reply(self.root, {'project': state}, 'plan'))['project']
        self.assertEqual(compact['presentation']['paths'][0], state['latest_sample']['path'])

    def test_independently_reviewed_partial_file_can_be_shown_as_draft_but_never_final(self):
        projects.create_plan(self.root, 'Product', [], requirements={'audio': True, 'video': True})
        projects.sync_acceptance(self.root, ['A complete product with an observed result'])
        current = projects.read_project(self.root)['acceptance']
        projects.execute_step(self.root, 'workspace', 'Failed packaging', '', lambda *a: json.dumps({
            'ok': False, 'error': 'Invalid handoff metadata', 'output_dir': str(self.product.parent),
            'available_files': [str(self.product)]}), purpose='preview')
        with self.assertRaises(ValueError):
            projects.create_plan(self.root, '', [], status='review', product_path=str(self.product))
        review={'product_path':str(self.product),'sha256':projects.digest(self.product),
                'contract_hash':current['hash'],'status':'needs_revision','criteria':[]}
        projects.execute_step(self.root, 'workspace', 'Review partial file', '', lambda *a: json.dumps({
            'ok': True,'quality_review':review,'handoff':{'output_files':[str(self.report)],'checks':[]}}),purpose='review')
        state=projects.create_plan(self.root,'',[],status='review',product_path=str(self.product))
        self.assertTrue(state['product_path'].endswith('result.txt'))
        self.assertEqual(state['quality_status'],'needs_revision')
        with self.assertRaises(ValueError):projects.create_plan(self.root,'',[],status='ready')
        self.product.write_text('Changed after review')
        with self.assertRaises(ValueError):projects.create_plan(self.root,'',[],status='review',product_path=str(self.product))

    def test_preview_defers_packaging_but_final_delivery_and_broken_zip_do_not(self):
        source = self.product.with_suffix('.ecproj')
        source.write_text('Fixture only: already checked by author')
        metadata = {'path': str(source), 'role': 'editable_source', 'format': 'ecproj',
            'reopen': {'status': 'passed', 'evidence': 'Declared fixture'}, 'limitations': []}
        handoff = {'task': 'Limited experiment', 'checks': [], 'delivery': {
            'source_status': 'included', 'source_note': 'Scoped source', 'files': [metadata]}}
        preview = build_delivery(handoff, source.parent, purpose='preview', native=False)
        self.assertEqual(preview['technical_status'], 'passed')
        self.assertEqual(len(preview['finalization_pending']), 1)
        self.assertFalse(projects.media_accepted(preview, {}))
        self.assertEqual(projects.delivery_summary(preview)['finalization_pending'], preview['finalization_pending'])
        final = build_delivery(handoff, source.parent, purpose='delivery', native=False)
        self.assertEqual(final['technical_status'], 'needs_revision')
        badzip = source.with_suffix('.zip'); badzip.write_text('Not a zip')
        handoff['delivery']['files'].append({**metadata, 'path': str(badzip), 'role': 'source_archive'})
        with self.assertRaises(zipfile.BadZipFile):
            build_delivery(handoff, source.parent, purpose='preview', native=False)

    def test_declared_resource_limit_keeps_checks_open_and_supplies_a_next_action(self):
        self.criteria=[self.criterion('request_fidelity','content','passed'),self.criterion('risk','functional','passed'),
            self.criterion('extent','technical','not_run'),self.criterion('perception','listening','not_run')]
        self.criteria[2]['blocked_by']='listening'
        self.report.write_text(json.dumps({'product_path':str(self.product),'criteria':self.criteria,
            'observation_limits':[{'method':'listening','reason':'No listening transport is connected.',
                'next_action':'Listen to the exact saved audio with the user before approving synchronization.'}]}))
        review=read_review({'source_files':[str(self.product)],'output_files':[str(self.report)]},self.out,self.root,'codex',self.acceptance)
        routed=continuation(review)
        self.assertEqual(review['status'],'needs_review');self.assertEqual(routed['action'],'request_user_verification')
        self.assertIn('exact saved audio',routed['next_actions'][0]['next_action'])
        self.assertFalse(needs_continuation({'status':'review','review_criteria':review['criteria'],'review_unavailable_methods':review['unavailable_methods']}))
