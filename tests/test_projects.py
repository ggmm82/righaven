"""Adaptive collaboration, recovery of real files and bounded outage handling."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from righaven import projects


VIDEO = [
    {'id': 'visual', 'agent': 'photocraft', 'goal': 'Texture del robot', 'depends_on': []},
    {'id': 'motion', 'agent': 'effectcraft', 'goal': 'Movimento del robot', 'depends_on': ['visual']},
    {'id': 'audio', 'agent': 'soundcraft', 'goal': 'Musica latina', 'depends_on': ['motion']},
    {'id': 'final', 'agent': 'filmcraft', 'goal': 'Video con musica', 'depends_on': ['motion', 'audio']},
]


class ProjectTests(unittest.TestCase):
    def test_nested_physical_workspace_is_not_mapped_twice_as_a_worker_path(self):
        with tempfile.TemporaryDirectory() as directory:
            virtual = Path(directory)
            workspace = virtual / 'outputs/conversation'
            file = workspace / 'outputs/filmcraft/final.mp4'
            file.parent.mkdir(parents=True)
            file.write_text('fixture')
            self.assertEqual(projects.workspace_path(workspace, file, worker_root=virtual), file)
            self.assertEqual(projects.workspace_path(workspace, virtual / 'outputs/filmcraft/final.mp4',
                                                    worker_root=virtual), file)
            self.assertIsNone(projects.workspace_path(workspace, '/etc/passwd', worker_root=virtual))
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / 'conversation'
        self.root.mkdir()
        self.counter = 0

    def tearDown(self):
        self.directory.cleanup()

    def plan(self, steps=None):
        return projects.create_plan(self.root, 'Robot che balla', steps if steps is not None else VIDEO, 'animated_video')

    def result(self, agent, *, ok=True, error='', extension='mp4'):
        self.counter += 1
        folder = self.root / 'outputs' / agent / ('job' + str(self.counter))
        folder.mkdir(parents=True)
        path = folder / ('result.' + extension)
        path.write_text('fixture file, not playable media')
        return {'ok': ok, 'error': error, 'output_dir': str(folder), 'available_files': [str(path)],
            'handoff': {'source_files': [], 'output_files': [str(path)], 'previews': [],
                'checks': [{'name': 'Riapertura', 'status': 'passed', 'evidence': 'fixture'}],
                'delivery': {'source_status': 'included', 'files': [{'path': str(path), 'reopen': {'status': 'passed'}}]}}}

    def run_step(self, sid, response, *, agent=None, capture=None, **kwargs):
        agent = agent or next(s['agent'] for s in VIDEO if s['id'] == sid)
        def invoke(task, started):
            if capture is not None:
                capture.append(task)
            started(response.get('output_dir', '/mnt/user-data/outputs/saved'))
            return json.dumps(response)
        return json.loads(projects.execute_step(self.root, agent, 'Esegui solo il lavoro utile', sid, invoke, **kwargs))

    def test_any_catalog_team_and_input_order_are_allowed(self):
        roles = projects.applications()
        self.assertIn("blender", {a["id"] for a in roles})
        steps = [{'id': 'task' + str(i), 'agent': app['id'], 'goal': app['role'],
                  'depends_on': ['task12'] if i == 0 else []} for i, app in enumerate(roles)]
        p = self.plan(steps)
        self.assertEqual(len(p['steps']), len(roles))
        # Even a video may start from existing source material and an integration role.
        p = self.plan([{'id': 'integrate', 'agent': 'filmcraft', 'goal': 'Monta gli input esistenti'}])
        self.assertTrue(any(s['id'] == 'integrate' for s in p['steps']))

    def test_new_catalog_tool_needs_no_new_model_configuration(self):
        with patch.object(projects, 'applications', return_value=projects.applications() + [{'id': 'newcraft'}]):
            p = projects.create_plan(self.root, 'Nuovo strumento', [{'id': 'new', 'agent': 'newcraft', 'goal': 'Prodotto'}])
        self.assertEqual(p['steps'][0]['agent'], 'newcraft')

    def test_upsert_reorders_reassigns_adds_and_skips_without_erasing_results(self):
        self.plan()
        r = self.result('photocraft')
        self.run_step('visual', r)
        p = self.plan([{'id': 'audio', 'agent': 'filmcraft', 'goal': 'Verifica audio già pronto'},
                       {'id': 'visual', 'agent': 'photocraft', 'goal': 'Asset già disponibili', 'status': 'skipped'},
                       {'id': 'preview', 'agent': 'filmcraft', 'goal': 'Prima bozza completa'}])
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'audio')['agent'], 'filmcraft')
        self.assertTrue(any(r['label'] == 'result.mp4' for r in p['results']))
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'visual')['attempt_count'], 1)

    def test_failed_audio_does_not_block_film_integration_or_optional_checks(self):
        self.plan()
        partial = self.result('soundcraft', ok=False, error='Limite dei turni DeepSeek raggiunto', extension='wav')
        partial.pop('handoff')
        self.run_step('audio', partial)
        captured = []
        final = self.result('filmcraft')
        final['handoff']['checks'].append({'name': 'GUI desktop', 'status': 'not_run', 'evidence': 'Solo CLI disponibile'})
        reply = self.run_step('final', final, capture=captured, purpose='integration')
        self.assertTrue(reply['ok'])
        self.assertIn(partial['available_files'][0], captured[0])
        self.assertIn('Scopo incarico: integration', captured[0])
        self.assertIn('GUI desktop', reply['review_notes'])
        p = projects.read_project(self.root)
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'audio')['status'], 'paused')
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'final')['status'], 'completed')

    def test_creative_revision_preserves_other_work_and_has_no_three_attempt_lifetime_cap(self):
        self.plan()
        self.run_step('visual', self.result('photocraft'))
        self.run_step('audio', self.result('soundcraft', extension='wav'))
        for _ in range(5):
            projects.revise_step(self.root, 'motion', 'Migliora la leggibilità della posa')
            self.assertTrue(self.run_step('motion', self.result('effectcraft'))['ok'])
        p = projects.read_project(self.root)
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'motion')['attempt_count'], 5)
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'audio')['status'], 'completed')

    def test_quota_stops_automatic_retries_but_new_service_or_user_turn_can_resume(self):
        self.plan()
        failure = {'ok': False, 'error': 'RESOURCE_EXHAUSTED: Individual quota reached'}
        profile = {'engine': 'gemini', 'model': 'fixture'}
        reply = self.run_step('motion', failure, provider=profile, request_id='user-one')
        self.assertEqual(reply['attention']['code'], 'provider_quota')
        denied = self.run_step('motion', self.result('effectcraft'), provider=profile, request_id='user-one')
        self.assertTrue(denied['retry_blocked'])
        allowed = self.run_step('motion', self.result('effectcraft'), provider={'engine': 'deepseek', 'model': 'fixture'}, request_id='user-one')
        self.assertTrue(allowed['ok'])
        self.run_step('motion', failure, provider=profile, request_id='user-two')
        resumed = self.run_step('motion', self.result('effectcraft'), provider=profile, request_id='explicit-continue')
        self.assertTrue(resumed['ok'])

    def test_repeated_identical_failures_without_files_stop_only_the_affected_activity(self):
        self.plan()
        failure = {'ok': False, 'error': 'Comando non supportato'}
        for _ in range(2):
            self.assertFalse(self.run_step('audio', failure)['ok'])
        blocked = self.run_step('audio', self.result('soundcraft'))
        self.assertTrue(blocked['retry_blocked'])
        self.assertTrue(self.run_step('final', self.result('filmcraft'), purpose='review')['ok'])
        projects.revise_step(self.root, 'audio', 'Usa i WAV già generati e correggi solo il mix')
        self.assertTrue(self.run_step('audio', self.result('soundcraft'))['ok'])

    def test_old_three_failure_plan_is_recoverable_and_does_not_need_archiving(self):
        self.plan()
        p = self.root / '.righaven-project/project.json'
        old = json.loads(p.read_text())
        old.pop('requirements')  # Installed versions before adaptive media acceptance.
        audio = next(s for s in old['steps'] if s['id'] == 'audio')
        saved = self.result('soundcraft', extension='wav')
        audio.update(status='needs_revision', attempts=[{'status': 'needs_revision', 'error': 'Limite dei turni',
            'output_files': saved['handoff']['output_files'], 'output_dir': saved['output_dir']} for _ in range(3)])
        p.write_text(json.dumps(old))
        self.assertEqual(projects.read_project(self.root)['requirements'], {'audio': True, 'video': True})
        self.assertTrue(self.run_step('final', self.result('filmcraft'), purpose='integration')['ok'])
        self.assertTrue(self.run_step('audio', self.result('soundcraft'), purpose='review')['ok'])

    def test_restart_keeps_saved_path_and_previous_usable_version(self):
        from righaven.progress import create_job, read_status, update
        self.plan()
        first = self.result('effectcraft')
        self.run_step('motion', first)
        progress = create_job(self.root, 'rh-job-0123456789ab', 'effectcraft', 'codex', 'fixture')
        update(progress, 'creating')
        def die(task, started):
            started('/mnt/user-data/outputs/effectcraft/rh-job-0123456789ab')
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            projects.execute_step(self.root, 'effectcraft', 'Revisione', 'motion', die)
        with patch.object(projects, 'GATEWAY_SESSION', 'new-process'):
            p = projects.read_project(self.root)
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'motion')['status'], 'paused')
        self.assertEqual(read_status(progress)['phase'], 'failed')
        self.assertTrue(p['results'])
        self.assertNotIn('gateway_session', json.dumps(p))

    def test_compact_project_memory_does_not_repeat_all_attempt_histories(self):
        self.plan()
        for _ in range(8):
            self.run_step('motion', self.result('effectcraft'))
        p = projects.read_project(self.root)
        self.assertLess(len(json.dumps(p)), 5000)
        self.assertNotIn('attempts', json.dumps(p))
        self.assertEqual(next(s for s in p['steps'] if s['id'] == 'motion')['attempt_count'], 8)

    def test_final_ready_requires_existing_output_and_independent_product_validation(self):
        self.plan()
        r = self.result('filmcraft')
        self.run_step('final', r, purpose='integration')
        product = r['handoff']['output_files'][0]
        with self.assertRaisesRegex(ValueError, 'purpose=delivery'):
            projects.create_plan(self.root, '', [], status='ready', product_path=product)
        r.update(product_verified=True, verified_products=[product])
        self.run_step('final', r, purpose='delivery')
        with self.assertRaisesRegex(ValueError, 'sorgenti incompleti'):
            projects.create_plan(self.root, '', [], status='ready', product_path=product)
        r['delivery_record'] = {'id': 'final-delivery', 'technical_status': 'passed',
            'requirements': {'video': True, 'audio': True}, 'verified_products': [product],
            'files': [{'path': product, 'sha256': projects.digest(product), 'role': 'export'}]}
        self.run_step('final', r, purpose='delivery')
        with self.assertRaisesRegex(ValueError, 'revisione separata'):
            projects.create_plan(self.root, '', [], status='ready', product_path=product)
        review = self.result('filmcraft', extension='json')
        review['quality_review'] = {'status': 'passed', 'product_path': product, 'sha256': projects.digest(product),
                                   'criteria': [{'method': 'visual', 'status': 'passed'}, {'method': 'listening', 'status': 'passed'}]}
        self.run_step('independent-review', review, agent='filmcraft', purpose='review')
        p = projects.create_plan(self.root, '', [], status='ready', product_path=product)
        self.assertEqual(p['status'], 'ready')
        self.assertEqual(p['deliveries'][0]['id'], 'final-delivery')
        self.assertTrue(p['deliveries'][0]['current'])
        negative = self.result('filmcraft', extension='json')
        negative['quality_review'] = {**review['quality_review'], 'status': 'needs_revision'}
        self.run_step('independent-review', negative, agent='filmcraft', purpose='review')
        with self.assertRaisesRegex(ValueError, 'revisione separata'):
            projects.create_plan(self.root, '', [], status='ready', product_path=product)
        Path(product).write_text('changed after review')
        with self.assertRaisesRegex(ValueError, 'sorgenti incompleti'):
            projects.create_plan(self.root, '', [], status='ready', product_path=product)
        with self.assertRaises(ValueError):
            projects.create_plan(self.root, '', [], status='ready', product_path='/etc/passwd')

    def test_files_are_scoped_to_the_conversation_and_archival_is_safe(self):
        self.plan()
        self.run_step('visual', self.result('photocraft'))
        branch = self.root.parent / 'branch'
        shutil.copytree(self.root, branch)
        self.assertIsNone(projects.read_project(branch))
        self.assertIsNone(projects.public_artifact(self.root, '/etc/passwd'))
        outside = self.root.parent / 'outside'; outside.mkdir()
        (outside / '.righaven-project').symlink_to(self.root / '.righaven-project', target_is_directory=True)
        with self.assertRaises(ValueError):
            projects.read_project(outside)
        archived = projects.archive_plan(self.root, 'Nuovo obiettivo dell’utente')
        self.assertTrue(archived['files_preserved'])
        self.assertIsNone(projects.read_project(self.root))
        self.plan()
        p = self.root / '.righaven-project/project.json'
        v = json.loads(p.read_text()); v['id'] = '../../outside'; p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):
            projects.archive_plan(self.root, 'Archive')

    def test_explicit_owner_acceptance_is_bound_to_complete_delivery_and_current_bytes(self):
        self.plan()
        response = self.result('filmcraft')
        product = response['handoff']['output_files'][0]
        response.update(product_verified=True, verified_products=[product], delivery_record={
            'id': 'version-two', 'technical_status': 'passed', 'requirements': {'audio': True, 'video': True},
            'verified_products': [product], 'files': [{'path': product, 'sha256': projects.digest(product), 'role': 'export'}]})
        self.run_step('final', response, purpose='delivery')
        with self.assertRaisesRegex(ValueError, 'cambiata'):
            projects.accept_delivery(self.root, 'old-version')
        accepted = projects.accept_delivery(self.root, 'version-two')
        self.assertEqual(accepted['quality_status'], 'accepted_by_user')
        self.assertEqual(accepted['status'], 'ready')
        Path(product).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'cambiati'):
            projects.accept_delivery(self.root, 'version-two')

    def test_final_delivery_tracks_transitive_contributions_and_excludes_unused_work(self):
        self.plan()
        visual, motion, unused, final = [self.result(agent) for agent in ('photocraft', 'effectcraft', 'soundcraft', 'filmcraft')]
        motion['handoff']['source_files'] = visual['handoff']['output_files']
        final['handoff']['source_files'] = motion['handoff']['output_files']
        final['verified_products'] = final['handoff']['output_files']
        for sid, reply in [('visual', visual), ('motion', motion), ('audio', unused), ('final', final)]:
            self.run_step(sid, reply, purpose='delivery' if sid == 'final' else 'work')
        deliveries = {d['agent']: d for d in projects.read_project(self.root)['deliveries']}
        self.assertTrue(deliveries['filmcraft']['current'])
        self.assertTrue(deliveries['effectcraft']['contribution'])
        self.assertTrue(deliveries['photocraft']['contribution'])
        self.assertFalse(deliveries['soundcraft']['contribution'])

    def test_simple_delegation_auto_tracks_activity_without_planning_ceremony(self):
        result = self.result('cadcraft', extension='dxf')
        response = self.run_step('', result, agent='cadcraft')
        self.assertTrue(response['ok'])
        p = projects.read_project(self.root)
        self.assertEqual(len(p['steps']), 1)
        self.assertEqual(p['steps'][0]['agent'], 'cadcraft')

    def test_selected_delivery_and_sources_survive_many_reviews_in_the_same_activity(self):
        projects.create_plan(self.root, 'Complete workbook', [])
        result = self.result('gridcraft', extension='xlsx')
        source = Path(result['output_dir']) / 'sources.zip';source.write_text('Declared fixture')
        result['handoff']['output_files'].append(str(source))
        result['verified_products'] = result['handoff']['output_files'][:1]
        self.run_step('shared', result, agent='gridcraft', purpose='delivery')
        selected = result['handoff']['output_files'][0]
        for _ in range(24):
            self.run_step('shared', self.result('gridcraft', extension='json'), agent='gridcraft', purpose='review')
        state = projects.read_project(self.root)
        paths = [r['path'] for r in state['results']]
        self.assertIn(projects.public_artifact(self.root, selected), paths)
        self.assertIn(projects.public_artifact(self.root, source), paths)
        self.assertEqual(state['results'][0]['path'], projects.public_artifact(self.root, selected))
        with projects.locked(self.root) as folder:
            saved = projects.load(folder, self.root)
        self.assertLessEqual(len(saved['steps'][0]['attempts']), projects.MAX_HISTORY)
        self.assertTrue(any(selected in r['files'] for r in projects.read_results(saved, self.root)))


if __name__ == '__main__':
    unittest.main()
