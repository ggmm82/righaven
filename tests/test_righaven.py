import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RigHavenTests(unittest.TestCase):
    def setUp(self):
        from righaven.resource_budget import ResourceBudget
        budget_patch = patch('righaven.resource_budget.BUDGET', ResourceBudget())
        budget_patch.start(); self.addCleanup(budget_patch.stop)
        publisher = patch('righaven.task_staging.TaskStaging.publish', side_effect=lambda result: result)
        publisher.start(); self.addCleanup(publisher.stop)
        self.temp = tempfile.TemporaryDirectory()
        os.environ['RIGHAVEN_STATE'] = self.temp.name
        from righaven import state
        self.state = importlib.reload(state)
        from righaven import docker_runtime, login, router
        self.runtime = importlib.reload(docker_runtime)
        from righaven.worker_slots import WorkerSlots
        workers=patch.object(self.runtime,"WORKERS",WorkerSlots());workers.start();self.addCleanup(workers.stop)
        self.state.atomic_json(self.state.STATE/"runtime.json",{"mode":"auto","max_workers":1})
        from righaven import runtime_settings
        host = patch.object(runtime_settings, 'capacity', return_value={'cpus': 4, 'memory_mib': 8192, 'detected': True})
        host.start()
        self.addCleanup(host.stop)
        importlib.reload(login)
        self.router = importlib.reload(router)
        (self.state.STATE / 'installation-id').write_text('test-installation')

    def tearDown(self):
        self.temp.cleanup()

    def connect_antigravity(self):
        root = self.state.credential_dir('gemini')
        (root / 'antigravity-cli').mkdir(exist_ok=True)
        (root / 'antigravity-cli/antigravity-oauth-token').write_text('fixture-native-token')
        (root / 'antigravity-account.json').write_text('{}')

    def test_configurable_engines_persist_without_credentials(self):
        self.state.update_agent('gridcraft', {'engine': 'gemini', 'model': 'custom-model',
                                            'instructions': 'Usa euro', 'enabled': True,
                                            'skills': ['skill-vectorcraft']})
        self.assertEqual(self.state.catalog()['gridcraft']['engine'], 'gemini')
        self.assertIn('skill-vectorcraft', self.state.catalog()['gridcraft']['skills'])
        self.assertIn('skill-gridcraft', self.state.catalog()['gridcraft']['skills'])
        self.assertFalse(self.state.connection_status('gemini'))
        self.assertEqual(set(self.state.catalog()), {app['id'] for app in self.state.applications()})

    def test_codex_payload_matches_current_cli_contract(self):
        from righaven.codex_compat import modernize_codex_payload
        original = {'model': 'gpt-5.4', 'tools': [{'type': 'function'}]}
        payload = modernize_codex_payload(original)
        self.assertEqual(payload['tool_choice'], 'auto')
        self.assertTrue(payload['parallel_tool_calls'])
        self.assertEqual(payload['include'], ['reasoning.encrypted_content'])
        self.assertNotIn('tool_choice', original)

    def test_existing_config_is_migrated_without_changing_model(self):
        from righaven import bootstrap
        bootstrap = importlib.reload(bootstrap)
        path = self.state.STATE / 'config.yaml'
        path.write_text('models:\n- name: rh-codex\n  use: righaven_core.models.openai_codex_provider:CodexChatModel\n  model: personal-model\n')
        os.environ['RIGHAVEN_PASSWORD'] = 'test-password-at-least-16-characters'
        with patch.object(bootstrap, 'catalog', return_value={}):
            bootstrap.initialize()
        config = __import__('yaml').safe_load(path.read_text())
        self.assertEqual(config['models'][0]['use'], 'righaven.codex_provider:HarnessCodexChatModel')
        self.assertEqual(config['models'][0]['model'], 'personal-model')

    def test_invalid_engine_and_unknown_specialist_rejected(self):
        for identifier, engine in [('unknown', 'codex'), ('gridcraft', 'shell')]:
            with self.assertRaises(ValueError):
                self.state.update_agent(identifier, {'engine': engine})

    def test_skill_paths_cannot_escape_the_catalog(self):
        with self.assertRaisesRegex(ValueError, 'Skill sconosciuta'):
            self.state.update_agent('gridcraft', {'engine': 'codex',
                                                'skills': ['../../credentials']})

    def test_volume_resolution_excludes_host_paths_and_traversal(self):
        self.runtime._mounts = [{'Destination': '/righaven-state', 'Source': '/host/state'}]
        self.assertEqual(self.runtime.host_path('/righaven-state/jobs/task.json'),
                         '/host/state/jobs/task.json')
        for path in ['/etc/passwd', '/righaven-state/../etc/passwd']:
            with self.assertRaises(ValueError):
                self.runtime.host_path(path)

    def test_internal_runtime_uses_only_shared_application_paths(self):
        shared = self.state.STATE / 'jobs' / 'task.json'
        shared.parent.mkdir(); shared.write_text('{}')
        with patch.dict(os.environ, {'RIGHAVEN_DOCKER_SCOPE':'internal',
                                     'RIGHAVEN_HOME':str(self.state.STATE/'righaven_core')}):
            self.assertEqual(self.runtime.host_path(shared), str(shared.resolve()))
            with self.assertRaisesRegex(ValueError, 'dati condivisi'):
                self.runtime.host_path('/etc/passwd')

    def test_internal_runtime_pulls_verified_software_only_when_missing(self):
        class Result:
            def __init__(self, code=0, stdout='', stderr=''):
                self.returncode=code;self.stdout=stdout;self.stderr=stderr
        calls=[]
        def run(argv, **kwargs):
            calls.append(argv)
            if argv[1:3]==['image','inspect'] and len(calls)==1:return Result(1)
            return Result()
        with patch.object(self.runtime.subprocess,'run',side_effect=run),patch.object(self.runtime,'docker',return_value='{}'):
            self.runtime.ensure_software_image()
        self.assertEqual(calls[1][:2], ['docker','pull'])

    def test_provider_session_never_advances_latest_implicitly(self):
        from righaven import environment_runtime,tool_versions
        with patch.object(tool_versions,'selections',return_value={'provider-agy':'latest'}), \
             patch.object(tool_versions,'resolved',return_value={'provider-agy':{'revision':'verified'}}) as resolved, \
             patch.object(environment_runtime,'ensure',return_value={'image_id':'sha256:ready'}) as ensure:
            self.assertEqual(self.runtime.provider_image('gemini'),'sha256:ready')
        self.assertFalse(resolved.call_args.kwargs['refresh'])
        ensure.assert_called_once()

    def test_container_uses_one_thread_and_no_docker_socket(self):
        credentials = self.state.credential_dir('codex')
        (credentials / 'auth.json').write_text('{}')
        workspace = Path(self.temp.name) / 'workspace'
        from righaven import runtime_settings
        limits = {'cpus': 2, 'memory_mib': 3072, 'tmp_mib': 768, 'threads': 2, 'max_workers':1}
        captured = []
        class Result:
            returncode = 0
            stdout = '{"ok": true}'
            stderr = ''
        def execute(argv, **kwargs):
            captured.append(argv)
            return Result()
        with patch.object(self.runtime, 'host_path', side_effect=lambda p: '/host/' + Path(p).name), \
             patch.object(self.runtime.subprocess, 'run', side_effect=execute), \
             patch.object(runtime_settings, 'effective', return_value=limits):
            result = self.runtime.delegate('gridcraft', 'Analizza il foglio', workspace)
        self.assertIn('true', result)
        argv = next(a for a in captured if a[:2] == ['docker', 'run'])
        self.assertIn('--memory=2304m', argv)
        self.assertIn('--cpus=1.25', argv)
        self.assertIn('RIGHAVEN_CPU_THREADS=2', argv)
        self.assertIn('--cap-drop=ALL', argv)
        self.assertFalse(any('docker.sock' in arg for arg in argv))
        self.assertTrue(any('dst=/mnt/user-data' in arg for arg in argv))
        self.assertEqual(captured[-1][:3], ['docker', 'rm', '-f'])
        self.assertFalse(self.runtime.WORKERS.locked())

    def test_dynamic_role_and_selected_cli_skills_enter_actual_worker_payload(self):
        from righaven import projects
        from righaven.project_skills import load_compiled
        from test_project_skills import role
        credentials = self.state.credential_dir('codex')
        (credentials / 'auth.json').write_text('{}')
        workspace = Path(self.temp.name) / 'workspace'
        projects.create_plan(workspace, 'Progetto con vincoli', [])
        projects.sync_acceptance(workspace, ['Vincoli effettivi del progetto'])
        spec = role(); spec['tools'] = ['cadcraft', 'gridcraft']
        projects.sync_project_context(workspace, [spec], {'decisione': 'Confrontare alternative'})
        project = projects.read_project(workspace); compiled = project['roles'][0]
        captured = []
        def execute(argv, **kwargs):
            if argv[:2] == ['docker', 'run']:
                payload = json.loads(next((self.state.STATE / 'jobs').glob('*.json')).read_text())
                captured.append(payload)
            return type('Result', (), {'returncode': 0, 'stdout': '{"ok":true}', 'stderr': ''})()
        with patch.object(self.runtime, 'host_path', return_value='/host/fixture'), \
             patch.object(self.runtime.subprocess, 'run', side_effect=execute):
            self.runtime.delegate('workspace', 'Confronta alternative', workspace, role=compiled, acceptance=project['acceptance'])
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]['compiled_skill'], load_compiled(workspace, compiled))
        self.assertEqual(captured[0]['skills'], ['skill-workspace', 'skill-cadcraft', 'skill-gridcraft'])
        self.assertEqual(captured[0]['model'], self.state.team()['model'])
        self.assertEqual(captured[0]['engine'], self.state.team()['engine'])
        with self.assertRaisesRegex(ValueError, 'richiesta corrente'):
            self.runtime.delegate('workspace', 'Incarico obsoleto', workspace, role=compiled, acceptance={'hash': 'changed'})
        self.state.update_agent('cadcraft', {'engine': 'inherit', 'enabled': False})
        with self.assertRaisesRegex(ValueError, 'disabilitato'):
            self.runtime.delegate('workspace', 'Incarico', workspace, role=compiled, acceptance=project['acceptance'])

    def test_workspace_without_declared_tools_receives_native_policy_and_binary_masks(self):
        from righaven import projects, capability_policy
        from test_project_skills import role
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        workspace = Path(self.temp.name) / 'workspace'
        projects.create_plan(workspace, 'Native capabilities', [])
        projects.sync_acceptance(workspace, ['Use only enabled tools'])
        spec = role(); spec['tools'] = []
        projects.sync_project_context(workspace, [spec])
        project = projects.read_project(workspace)
        scoped = capability_policy.policy_from_names({'skill-' + a['id'] for a in self.state.applications()
                                                       if a['id'] != 'blender'})
        scoped.update(user_id='fixture-owner', agent_name=None, skill_names=['skill-workspace'], extra_skills=[],
            skill_sources={'skill-workspace': str(Path(__file__).resolve().parents[1] / 'skills/custom/skill-workspace')})
        calls, payloads = [], []
        def execute(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ['docker', 'run']:
                payloads.append(json.loads(next((self.state.STATE / 'jobs').glob('*.json')).read_text()))
            return type('Result', (), {'returncode': 0, 'stdout': '{"ok":true}', 'stderr': ''})()
        with patch('righaven.capability_policy.native_policy', return_value=scoped), \
             patch.object(self.runtime, 'host_path', return_value='/host/fixture'), \
             patch.object(self.runtime.subprocess, 'run', side_effect=execute):
            self.runtime.delegate('workspace', 'Work with base tools', workspace, role=project['roles'][0],
                                  acceptance=project['acceptance'], capability_policy=scoped)
        argv = next(c for c in calls if c[:2] == ['docker', 'run'])
        self.assertIn('/opt/righaven/apps/blender:ro,size=1m', argv)
        self.assertTrue(any('dst=/mnt/skills/custom,readonly' in a for a in argv))
        self.assertEqual(set(payloads[0]['capability_policy']['blocked']),{a['id'] for a in self.state.applications()})
        self.assertEqual(payloads[0]['capability_policy']['allowed'],[])
        self.assertEqual(payloads[0]['role']['tools'], [])
        self.assertFalse(list((self.state.STATE / 'jobs').glob('*-skills')))

    def test_native_disable_while_queued_is_checked_again_before_a_worker_starts(self):
        from righaven import capability_policy
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        available = capability_policy.policy_from_names({'skill-blender'})
        available.update(user_id='fixture-owner', agent_name=None, skill_names=['skill-blender'], extra_skills=[])
        disabled = {**available, **capability_policy.policy_from_names(set())}
        with patch('righaven.capability_policy.native_policy', side_effect=[available, disabled]), \
             patch.object(self.runtime.subprocess, 'run', return_value=type('R', (), {'returncode':0,'stdout':'{}','stderr':''})()) as run:
            with self.assertRaisesRegex(ValueError, 'disabilitato'):
                self.runtime.delegate('blender', 'Queued work', Path(self.temp.name) / 'workspace', capability_policy=available)
        self.assertFalse(any(call.args[0][:2] == ['docker', 'run'] for call in run.call_args_list))

    def test_gemini_coordinator_has_no_workspace_and_cleans_up_before_delegation(self):
        self.connect_antigravity()
        captured = []
        def execute(args, **kwargs):
            captured.append(args)
            job = next((self.state.STATE / 'jobs').glob('*.json'))
            self.assertEqual(json.loads(job.read_text())['model'], 'gemini-2.5-pro')
            return type('Result', (), {'returncode': 0, 'stdout': '{"ok":true,"response":{"candidates":[]}}'})()
        with patch.object(self.runtime, 'host_path', return_value='/host/private'), \
             patch.object(self.runtime.subprocess, 'run', side_effect=execute), patch.object(self.runtime, 'remove'):
            result = self.runtime.generate_gemini({'model': 'gemini-2.5-pro', 'contents': []})
        self.assertEqual(result, {'candidates': []})
        self.assertFalse(any('dst=/mnt/user-data' in arg or 'docker.sock' in arg for arg in captured[0]))
        self.assertTrue(any('dst=/credentials' in arg for arg in captured[0]))
        self.assertFalse(list((self.state.STATE / 'jobs').glob('*.json')))
        self.assertFalse(self.runtime.WORKERS.locked())

    def test_gemini_provider_errors_are_sanitized_and_release_admission(self):
        self.connect_antigravity()
        result = type('Result', (), {'returncode': 1, 'stdout': '{"ok":false,"error":"fixture-private-token"}'})()
        with patch.object(self.runtime, 'host_path', return_value='/host/private'), \
             patch.object(self.runtime.subprocess, 'run', return_value=result), patch.object(self.runtime, 'remove'):
            with self.assertRaisesRegex(RuntimeError, 'Antigravity non disponibile') as failure:
                self.runtime.generate_gemini({'model': 'gemini-2.5-pro'})
        self.assertNotIn('fixture-private-token', str(failure.exception))
        self.assertFalse(self.runtime.WORKERS.locked())

    def test_worker_timeout_reclaims_container_and_releases_admission(self):
        import subprocess
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 1)), \
             patch.object(self.runtime, 'remove') as remove:
            result = json.loads(self.runtime.delegate('wordcraft', 'Crea documento', Path(self.temp.name) / 'work'))
            self.assertFalse(result['ok'])
            self.assertTrue(result['partial'])
            self.assertIn('/mnt/user-data/outputs/wordcraft/rh-job-', result['output_dir'])
            self.assertEqual(result['staging_status'], 'quarantined')
        remove.assert_called_once()
        self.assertFalse(self.runtime.WORKERS.locked())
        from righaven.progress import list_jobs
        status = list_jobs(Path(self.temp.name) / 'work')[0]
        self.assertTrue(status['resources_reclaimed'])
        self.assertTrue(status['cleanup_started_at'])
        self.assertTrue(status['cleanup_finished_at'])

    def test_cancelled_queued_job_cannot_start_or_stop_an_unrelated_worker(self):
        import threading
        from righaven.cancellation import CURRENT
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        event = threading.Event(); event.set()
        token = CURRENT.set(event)
        self.runtime.WORKERS.acquire()
        try:
            with patch.object(self.runtime.subprocess, 'run') as run:
                result = json.loads(self.runtime.delegate('wordcraft','Queued',Path(self.temp.name)/'work'))
                self.assertFalse(result['ok'])
                run.assert_not_called()
            self.assertTrue(self.runtime.WORKERS.locked())
        finally:
            self.runtime.WORKERS.release()
            CURRENT.reset(token)

    def test_stop_of_owned_queued_job_never_inspects_or_stops_the_active_container(self):
        from righaven.progress import create_job, read_status
        workspace=Path(self.temp.name)/'queued-chat'
        progress=create_job(workspace,'rh-job-123456abcdef','workspace','codex','test')
        with patch.object(self.runtime,'docker') as docker:
            result=self.runtime.request_stop(workspace,'rh-job-123456abcdef')
        self.assertTrue(result['queued'])
        self.assertTrue(read_status(progress)['cancel_requested'])
        docker.assert_not_called()

    def test_run_cancellation_stops_its_label_checked_docker_worker_and_reclaims_resources(self):
        import asyncio, threading
        from types import SimpleNamespace
        from righaven.cancellation import call
        from righaven.progress import list_jobs, workspace_key
        workspace = Path(self.temp.name)/'work'
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        ready, stopped = threading.Event(), threading.Event()
        def execute(args, **kwargs):
            name = args[args.index('--name')+1]
            output = next((self.state.STATE/'task-staging').glob('*/'+name+'/output'))
            (output/'saved.txt').write_text('keep')
            ready.set()
            self.assertTrue(stopped.wait(3), 'Docker worker was left running')
            return SimpleNamespace(returncode=1,stdout='',stderr='worker stopped')
        def docker(*args, **kwargs):
            if args[0]=='inspect':
                return json.dumps({'Config':{'Labels':{'org.righaven.harness.installation':'test-installation','org.righaven.harness.workspace':workspace_key(workspace)}},'State':{'Running':True}})
            self.assertEqual(args[:3],('stop','--time','10'))
            stopped.set(); return ''
        async def scenario():
            task = asyncio.create_task(call(self.runtime.delegate,'wordcraft','Create',workspace))
            for _ in range(100):
                if ready.is_set(): break
                await asyncio.sleep(.01)
            self.assertTrue(ready.is_set())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await asyncio.wait_for(task,4)
        with patch.object(self.runtime,'host_path',return_value='/host/path'), \
             patch.object(self.runtime.subprocess,'run',side_effect=execute), \
             patch.object(self.runtime,'docker',side_effect=docker), \
             patch.object(self.runtime,'remove') as remove:
            asyncio.run(scenario())
        remove.assert_called_once()
        self.assertFalse(self.runtime.WORKERS.locked())
        self.assertEqual(next((self.state.STATE/'task-staging').rglob('saved.txt')).read_text(),'keep')
        status = list_jobs(workspace)[0]
        self.assertTrue(status['cancel_requested'])
        self.assertTrue(status['resources_reclaimed'])
        self.assertEqual(status['error_code'],'work_cancelled')

    def test_only_auth_files_are_copied_and_links_rejected(self):
        from righaven.run_agent import copy_credentials
        source = Path(self.temp.name) / 'source'
        destination = Path(self.temp.name) / 'dest'
        source.mkdir()
        (source / 'auth.json').write_text('{}')
        (source / 'history.json').write_text('private history')
        copy_credentials(source, destination, 'codex')
        self.assertEqual(list(p.name for p in destination.iterdir()), ['auth.json'])
        (source / 'auth.json').unlink()
        (source / 'auth.json').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            copy_credentials(source, destination, 'codex')

    def test_unconfirmed_cleanup_blocks_new_worker(self):
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        class Result:
            returncode = 0
            stdout = '{"ok":true}'
            stderr = ''
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', return_value=Result()), \
             patch.object(self.runtime, 'remove', side_effect=RuntimeError('cleanup failed')):
            with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
                self.runtime.delegate('gridcraft', 'Analizza', Path(self.temp.name) / 'work')
        self.assertTrue(self.runtime.WORKERS.locked())
        self.runtime.WORKERS.release()
        from righaven.progress import list_jobs
        status = list_jobs(Path(self.temp.name) / 'work')[0]
        self.assertTrue(status['cleanup_error'])
        self.assertFalse(status['resources_reclaimed'])

    def test_lifecycle_telemetry_failure_does_not_prevent_resource_reclamation(self):
        from types import SimpleNamespace
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        original = self.runtime.update
        def update(*args, **fields):
            if any(k in fields for k in ('worker_exit_at', 'cleanup_started_at', 'cleanup_finished_at')):
                raise OSError('Telemetry unavailable')
            return original(*args, **fields)
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr='')), \
             patch.object(self.runtime, 'update', side_effect=update), \
             patch.object(self.runtime, 'remove') as remove:
            self.assertTrue(json.loads(self.runtime.delegate('gridcraft', 'Analyze', Path(self.temp.name) / 'work'))['ok'])
        self.assertEqual(remove.call_count, 2)
        self.assertFalse(self.runtime.WORKERS.locked())

    def test_long_worker_response_remains_valid_json(self):
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        class Result:
            returncode = 0
            stdout = json.dumps({'ok': True, 'response': 'x' * 30000})
            stderr = ''
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', return_value=Result()), \
             patch.object(self.runtime, 'remove'):
            result = self.runtime.delegate('gridcraft', 'Analizza', Path(self.temp.name) / 'work')
        self.assertEqual(len(json.loads(result)['response']), 30000)

    def test_deepseek_credentials_are_read_only_and_absent_from_job(self):
        key = 'test-only-api-credential'
        (self.state.credential_dir('deepseek') / 'api.json').write_text(json.dumps({'api_key': key}))
        self.state.update_agent('gridcraft', {'engine': 'deepseek', 'model': 'deepseek-flash'})
        captured = []
        class Result:
            returncode = 0
            stdout = '{"ok":true}'
            stderr = ''
        def execute(argv, **kwargs):
            captured.append(argv)
            jobs = list((self.state.STATE / 'jobs').glob('*.json'))
            self.assertEqual(len(jobs), 1)
            self.assertNotIn(key, jobs[0].read_text())
            return Result()
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', side_effect=execute), \
             patch.object(self.runtime, 'remove'):
            self.runtime.delegate('gridcraft', 'Analizza', Path(self.temp.name) / 'work')
        self.assertTrue(any('dst=/credentials,readonly' in arg for arg in captured[0]))

    def test_unsuccessful_worker_json_is_not_reported_as_success(self):
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        class Result:
            returncode = 0
            stdout = '{"ok":false}'
            stderr = ''
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', return_value=Result()), \
             patch.object(self.runtime, 'remove'):
            with self.assertRaisesRegex(RuntimeError, 'completamento'):
                self.runtime.delegate('gridcraft', 'Analizza', Path(self.temp.name) / 'work')
        self.assertFalse(self.runtime.WORKERS.locked())

    def test_login_setup_errors_release_admission(self):
        from righaven import login
        for failing_operation in ('credential_dir', 'pty.openpty'):
            with self.subTest(operation=failing_operation), \
                 patch('righaven.login.' + failing_operation, side_effect=OSError('setup failed')):
                with self.assertRaises(OSError):
                    login.LoginSession('gemini')
            self.assertFalse(self.runtime.WORKERS.locked())

    def test_browser_api_rejects_cross_origin_configuration(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.router.router)
        client = TestClient(app)
        payload = {'engine': 'gemini', 'model': '', 'instructions': '', 'enabled': True}
        response = client.put('/harness/api/agents/gridcraft', json=payload,
                              headers={'origin': 'https://other.example'})
        self.assertEqual(response.status_code, 403)
        response = client.put('/harness/api/agents/gridcraft', json=payload,
                              headers={'origin': 'http://testserver'})
        self.assertEqual(response.status_code, 200)
        catalog = client.get('/harness/api/catalog').json()
        self.assertNotIn('auth.json', json.dumps(catalog))
        self.assertEqual(catalog['agents']['gridcraft']['engine'], 'gemini')

    def test_dynamic_audio_job_receives_the_actual_decoder_skill_without_loading_unrelated_tools(self):
        from righaven import capability_policy,environment_runtime
        root=Path(__file__).resolve().parents[1]
        names=['skill-workspace','skill-soundcraft','skill-ffmpeg']
        scope=capability_policy.policy_from_names(set(names))
        scope.update(user_id='owner',agent_name=None,skill_names=names,extra_skills=[],skill_sources={name:str(root/'skills/custom'/name) for name in names})
        payloads=[]
        def execute(argv,**kwargs):
            if argv[:2]==['docker','run']:payloads.append(json.loads(next((self.state.STATE/'jobs').glob('*.json')).read_text()))
            return type('Result',(),{'returncode':0,'stdout':'{"ok":true}','stderr':''})()
        ready={'id':'a'*64,'image':'fixture','image_id':'sha256:fixture','tools':['ffmpeg','soundcraft'],'status':'ready'}
        with patch('righaven.capability_policy.native_policy',return_value=scope),patch.object(self.runtime,'connection_status',return_value=True),patch.object(environment_runtime,'enabled',return_value=True),patch.object(environment_runtime,'ensure',return_value=ready),patch.object(self.runtime,'host_path',return_value='/host/fixture'),patch.object(self.runtime.subprocess,'run',side_effect=execute):
            self.runtime.delegate('soundcraft','Create editable audio',Path(self.temp.name)/'workspace',capability_policy=scope)
        self.assertEqual(set(payloads[0]['skills']),set(names))
        self.assertEqual(payloads[0]['capability_policy']['installed'],['ffmpeg','soundcraft'])


if __name__ == '__main__':
    unittest.main()
