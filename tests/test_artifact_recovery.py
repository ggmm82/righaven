"""Saved work can survive a provider failure without another generation."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from righaven import run_agent, docker_runtime, progress, projects


class ArtifactRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = {'agent': 'workspace', 'run_id': 'rh-job-123456abcdef', 'engine': 'codex', 'purpose': 'delivery'}
        self.out = self.root/'outputs/workspace'/self.job['run_id']; self.out.mkdir(parents=True)
        self.file = self.out/'analysis.txt'; self.file.write_text('Observed result')
        self.manifest = {'task': 'Analysis', 'source_files': [], 'output_files': [str(self.file)], 'previews': [],
            'checks': [{'name': 'Read content', 'status': 'passed', 'evidence': 'Observed result'}], 'warnings': [],
            'delivery': {'source_status': 'not_applicable', 'source_note': 'Report only', 'files': [{
                'path': str(self.file), 'role': 'report', 'format': 'TXT', 'open_with': 'Text editor',
                'editability': 'Editable report', 'reopen': {'status': 'passed', 'evidence': 'Read content'}, 'limitations': []}]}}
        (self.out/'handoff.json').write_text(json.dumps(self.manifest))

    def test_saved_report_is_validated_without_calling_a_model_and_missing_files_stay_invalid(self):
        with patch.object(run_agent, 'copy_credentials', side_effect=AssertionError('No credentials')):
            result = run_agent.finalize_saved(self.job, self.out, self.root)
        self.assertTrue(result['ok'])
        self.assertEqual(result['delivery_record']['technical_status'], 'passed')
        self.assertIsNone(result['quality_review'])
        self.assertEqual(self.file.read_text(), 'Observed result')
        self.file.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            run_agent.finalize_saved(self.job, self.out, self.root)

    def test_new_review_findings_are_checked_before_the_worker_finishes(self):
        report=self.out/'quality-review.json'
        report.write_text(json.dumps({'review_version':2,'criteria':[{'requirement_id':'layout','status':'failed'}],
            'findings':[{'requirement_id':'layout','severity':'advisory','location':'Cover',
                         'evidence':'Different spacing might look nicer','impact':'Optional preference'}]}))
        self.manifest['output_files'].append(str(report))
        self.manifest['delivery']['files'].append({**self.manifest['delivery']['files'][0],'path':str(report),'format':'JSON'})
        (self.out/'handoff.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError,'blocking'):
            run_agent.validate_handoff(self.out,self.root,require_delivery=True)
        self.assertEqual(self.file.read_text(),'Observed result')

    def test_finalize_entrypoint_never_loads_accounts_or_starts_a_provider(self):
        import contextlib, io, sys
        original_path = Path
        def scoped(value):
            p = original_path(value)
            if p == original_path('/mnt/user-data'):
                return self.root
            if p.is_relative_to('/mnt/user-data'):
                return self.root/p.relative_to('/mnt/user-data')
            return p
        jobfile=self.root/'job.json';jobfile.write_text(json.dumps(self.job))
        stream=io.StringIO()
        with patch.object(sys,'argv',['run_agent.py','--finalize',str(jobfile)]), \
             patch.object(run_agent,'Path',side_effect=scoped), \
             patch.object(run_agent,'copy_credentials',side_effect=AssertionError('No account access')), \
             patch('righaven.codex_native.run',side_effect=AssertionError('No model call')), \
             contextlib.redirect_stdout(stream):
            self.assertEqual(run_agent.main(),0)
        self.assertTrue(json.loads(stream.getvalue())['ok'])

    def test_outer_recovery_reuses_policy_and_image_without_credentials_or_ai_command(self):
        path = progress.create_job(self.root, self.job['run_id'], 'workspace', 'codex', 'fixture')
        progress.update(path, 'failed')
        args = ['run', '--name', self.job['run_id'], '--cap-drop=ALL', '--memory=1024m',
                '--tmpfs', '/opt/righaven/apps/blender:ro,size=1m',
                '--mount', 'type=bind,src=/account,dst=/credentials',
                '--mount', 'type=bind,src=/workspace,dst=/mnt/user-data',
                '--mount', 'type=bind,src=/job,dst=/job.json,readonly',
                'image@sha256:fixture', 'python3', '/opt/righaven-worker/run_agent.py', '/job.json']
        def verify(command, **kwargs):
            self.assertNotIn('type=bind,src=/account,dst=/credentials', command)
            self.assertIn('/opt/righaven/apps/blender:ro,size=1m', command)
            self.assertEqual(command[-4:], ['python3', '/opt/righaven-worker/run_agent.py', '--finalize', '/job.json'])
            self.assertEqual(kwargs['timeout'], 300)
            return subprocess.CompletedProcess(command, 0, json.dumps(run_agent.finalize_saved(self.job, self.out, self.root)), '')
        with patch.object(docker_runtime, 'docker', return_value='{"OOMKilled":false}'), \
             patch.object(docker_runtime, 'remove') as remove, \
             patch.object(docker_runtime.subprocess, 'run', side_effect=verify), \
             patch('righaven.capability_policy.native_policy',return_value={'allowed':['d2','blender']}), \
             patch.object(projects, 'read_project', return_value=None):
            result = docker_runtime.recover_saved(args, path, self.root,
                '/mnt/user-data/outputs/workspace/'+self.job['run_id'], 'Usage limit exceeded',
                policy={'source':'righaven_core','user_id':'owner','allowed':['d2'],'execution_scope':'role'})
        self.assertTrue(result['ok']); self.assertEqual(result['recovery']['status'], 'verified')
        self.assertEqual(result['attention']['code'], 'provider_quota'); remove.assert_called_once()
        self.assertEqual(progress.public_status(progress.read_status(path))['artifact_recovery']['status'], 'verified')

    def test_cancelled_auth_failed_and_oom_jobs_do_not_trigger_recovery(self):
        path = progress.create_job(self.root, self.job['run_id'], 'workspace', 'codex', 'fixture')
        output = '/mnt/user-data/outputs/workspace/'+self.job['run_id']
        with patch.object(docker_runtime, 'remove') as remove:
            self.assertIsNone(docker_runtime.recover_saved([], path, self.root, output, 'Unauthorized'))
            progress.update(path, cancel_requested=True)
            self.assertIsNone(docker_runtime.recover_saved([], path, self.root, output, 'Usage limit exceeded'))
            remove.assert_not_called()
        progress.update(path, cancel_requested=False)
        with patch.object(docker_runtime, 'docker', return_value='{"OOMKilled":true}'), \
             patch.object(docker_runtime, 'remove') as remove, patch.object(projects, 'read_project', return_value=None):
            self.assertIsNone(docker_runtime.recover_saved(['--name', self.job['run_id']], path, self.root, output, 'Usage limit exceeded'))
            remove.assert_not_called()

    def test_symlink_destination_cannot_overwrite_an_input(self):
        outside = self.root/'input.json'; outside.write_text('keep')
        (self.out/'delivery-manifest.json').symlink_to(outside)
        with self.assertRaises(ValueError):run_agent.finalize_saved(self.job, self.out, self.root)
        self.assertEqual(outside.read_text(), 'keep')
