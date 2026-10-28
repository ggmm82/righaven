"""Verify one configuration actually reaches coordination and specialist jobs."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


class TeamTests(unittest.TestCase):
    def setUp(self):
        from righaven.resource_budget import ResourceBudget
        budget = patch('righaven.resource_budget.BUDGET', ResourceBudget()); budget.start(); self.addCleanup(budget.stop)
        publisher = patch('righaven.task_staging.TaskStaging.publish', side_effect=lambda result: result)
        publisher.start(); self.addCleanup(publisher.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'RIGHAVEN_STATE': self.temp.name,
            'RIGHAVEN_PASSWORD': 'test-password-at-least-16-characters'})
        self.environment.start()
        self.native_models = patch('righaven.docker_runtime.codex_models', return_value=[
            {'id': 'gpt-5.4', 'label': 'GPT-5.4', 'default': True}])
        from righaven import state, bootstrap, router, docker_runtime
        self.state = importlib.reload(state)
        self.bootstrap = importlib.reload(bootstrap)
        self.bootstrap.initialize()
        self.runtime = importlib.reload(docker_runtime)
        from righaven import runtime_settings
        host = patch.object(runtime_settings, 'capacity', return_value={'cpus': 4, 'memory_mib': 8192, 'detected': True})
        host.start()
        self.addCleanup(host.stop)
        self.native_models.start()
        self.router = importlib.reload(router)
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.router.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.native_models.stop()
        self.environment.stop()
        self.temp.cleanup()

    def save(self, **values):
        return self.client.put('/harness/api/team', json=values, headers={'origin': 'http://testserver'})

    def connect_antigravity(self):
        root = self.state.credential_dir('gemini')
        (root / 'antigravity-cli').mkdir(exist_ok=True)
        (root / 'antigravity-cli/antigravity-oauth-token').write_text('fixture-native-token')
        (root / 'antigravity-account.json').write_text('{}')

    def test_codex_catalog_ids_and_labels_are_distinct_and_invalid_names_are_not_saved(self):
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        entries = [{'id': 'gpt-6.1-sol', 'label': 'GPT-6.1-Sol', 'default': True}]
        with patch.object(self.runtime, 'codex_models', return_value=entries):
            response = self.client.get('/harness/api/team/models?engine=codex')
            self.assertEqual(response.json()['models'], ['gpt-6.1-sol'])
            self.assertEqual(self.save(engine='codex', model='GPT-6.1 Sol').status_code, 400)
            self.assertEqual(self.save(engine='codex', model='gpt-5.4').status_code, 400)
            self.assertEqual(self.save(engine='codex', model='GPT-6.1-Sol').status_code, 200)
        self.assertEqual(self.state.team()['model'], 'gpt-6.1-sol')

    def test_single_save_resets_legacy_overrides_preserves_skills_and_reaches_worker(self):
        self.state.update_agent('wordcraft', {'engine': 'gemini', 'model': 'legacy-model',
            'instructions': 'Italiano, stile sobrio', 'skills': ['skill-gridcraft'], 'enabled': False})
        with patch('righaven.deepseek.models', return_value=['deepseek-flash']):
            response = self.save(engine='deepseek', api_key='test-team-private-key')
        self.assertEqual(response.status_code, 200)
        data = self.client.get('/harness/api/catalog').json()
        self.assertEqual(data['team'], {'engine': 'deepseek', 'model': 'deepseek-flash', 'ready': True})
        self.assertEqual(set(data['effective_agents']), {app['id'] for app in self.state.applications()})
        for identifier, settings in data['effective_agents'].items():
            self.assertEqual((settings['engine'], settings['model']), ('deepseek', 'deepseek-flash'))
            self.assertIn('skill-' + identifier, settings['skills'])
            self.assertIn('skill-workspace', settings['skills'])
        self.assertFalse(data['agents']['wordcraft']['enabled'])
        self.assertEqual(data['agents']['wordcraft']['instructions'], 'Italiano, stile sobrio')
        self.assertIn('skill-gridcraft', data['agents']['wordcraft']['skills'])
        self.assertNotIn('test-team-private-key', json.dumps(data))
        captured = []
        def run(*args, **kwargs):
            captured.append(json.loads(next((self.state.STATE / 'jobs').glob('*.json')).read_text()))
            return type('Result', (), {'returncode': 0, 'stdout': '{"ok": true}', 'stderr': ''})()
        with patch.object(self.runtime, 'host_path', return_value='/host/path'), \
             patch.object(self.runtime.subprocess, 'run', side_effect=run), \
             patch.object(self.runtime, 'remove'):
            self.runtime.delegate('gridcraft', 'Prepara il foglio', Path(self.temp.name) / 'work')
        self.assertEqual(captured[0]['model'], 'deepseek-flash')
        self.assertEqual(captured[0]['engine'], 'deepseek')
        self.assertNotIn('test-team-private-key', json.dumps(captured))
        profile = yaml.safe_load((self.state.STATE / 'config.yaml').read_text())['models'][0]
        self.assertEqual(profile['name'], 'rh-codex')  # stable conversation identity
        self.assertEqual(profile['display_name'], 'RigHaven Harness')
        self.assertEqual(profile['model'], captured[0]['model'])
        self.assertEqual(profile['use'], 'righaven.deepseek_provider:HarnessDeepSeekChatModel')

    def test_change_model_without_reentering_key_and_restart_keep_all_in_sync(self):
        with patch('righaven.deepseek.models', return_value=['deepseek-flash', 'deepseek-pro']):
            self.assertEqual(self.save(engine='deepseek', api_key='test-team-key').status_code, 200)
            self.assertEqual(self.client.get('/harness/api/team/models').json(), {'models': ['deepseek-flash', 'deepseek-pro']})
            self.assertEqual(self.save(engine='deepseek', model='deepseek-pro').status_code, 200)
        self.bootstrap.initialize()
        for settings in self.client.get('/harness/api/catalog').json()['effective_agents'].values():
            self.assertEqual((settings['engine'], settings['model']), ('deepseek', 'deepseek-pro'))
        self.assertEqual(self.state.team()['engine'], 'deepseek')
        # Switching accounts keeps the same chat profile and skills.
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        self.assertEqual(self.save(engine='codex').status_code, 200)
        self.assertTrue(all(s['engine'] == 'codex' and s['model'] == 'gpt-5.4'
            for s in self.client.get('/harness/api/catalog').json()['effective_agents'].values()))
        self.assertEqual(len(yaml.safe_load((self.state.STATE / 'config.yaml').read_text())['models']), 1)

    def test_antigravity_shared_model_migrates_old_google_login(self):
        self.assertEqual(self.save(engine='gemini').status_code, 400)
        (self.state.credential_dir('gemini') / 'oauth_creds.json').write_text('{}')
        self.assertFalse(self.state.connection_status('gemini'))
        self.connect_antigravity()
        available=[{'id':'gemini-custom','label':'Fixture model','default':True}]
        with patch('righaven.docker_runtime.antigravity_models',return_value=available):
            response=self.save(engine='gemini')
            self.assertEqual(response.status_code,200)
            self.bootstrap.initialize()
            catalog=self.client.get('/harness/api/catalog').json()
            self.assertEqual(catalog['team'],{'engine':'gemini','model':'auto','ready':True})
            self.assertTrue(all(a['model']=='auto' for a in catalog['effective_agents'].values()))
            self.assertEqual(self.save(engine='gemini',model='gemini-custom').status_code,200)
            self.assertEqual(self.save(engine='gemini',model='unknown').status_code,400)
            self.assertEqual(self.client.get('/harness/api/team/models?engine=gemini').json()['models'],['auto','gemini-custom'])
        self.assertTrue(all(a['model']=='gemini-custom' for a in self.client.get('/harness/api/catalog').json()['effective_agents'].values()))

    def test_upgrade_resets_old_google_model_but_retains_other_provider_and_preferences(self):
        self.bootstrap.configure_team('gemini', 'gemini-2.5-pro')
        self.state.update_agent('cadcraft', {'engine': 'gemini', 'model': 'old-custom',
            'instructions': 'Consegna DXF', 'enabled': True})
        (self.state.STATE / 'google-provider-antigravity-v1').unlink()
        (self.state.credential_dir('gemini') / 'oauth_creds.json').write_text('{}')
        self.bootstrap.initialize()
        self.assertEqual(self.state.team(), {'engine': 'gemini', 'model': 'auto', 'ready': False})
        self.assertEqual(self.state.effective_agent('cadcraft')['model'], 'auto')
        self.assertEqual(self.state.effective_agent('cadcraft')['instructions'], 'Consegna DXF')
        self.bootstrap.configure_team('gemini', 'gemini-new-choice')
        self.bootstrap.initialize()
        self.assertEqual(self.state.team()['model'], 'gemini-new-choice')

    def test_invalid_connection_or_model_never_partially_changes_team(self):
        before = (self.state.STATE / 'config.yaml').read_bytes()
        self.assertEqual(self.save(engine='codex').status_code, 400)
        self.assertEqual(self.save(engine='deepseek').status_code, 400)
        with patch('righaven.deepseek.models', return_value=['deepseek-flash']):
            self.assertEqual(self.save(engine='deepseek', api_key='test-key', model='unknown').status_code, 400)
        self.assertEqual((self.state.STATE / 'config.yaml').read_bytes(), before)
        self.assertFalse(self.state.connection_status('deepseek'))
        with patch('righaven.deepseek.models') as models:
            response = self.client.put('/harness/api/team', json={'engine': 'deepseek', 'api_key': 'test-key'},
                headers={'origin': 'https://other.example'})
        self.assertEqual(response.status_code, 403)
        models.assert_not_called()

    def test_upgrade_removes_placeholder_writers_and_preserves_active_provider(self):
        with patch('righaven.deepseek.models', return_value=['deepseek-flash']):
            self.assertEqual(self.save(engine='deepseek', api_key='test-team-key').status_code, 200)
        path = self.state.STATE / 'config.yaml'
        content = yaml.safe_load(path.read_text())
        content['lead_prompt_overlay']['append'] = 'Sei la RigHaven Harness. Old delivery instructions.'
        content['tools'].extend([
            {'name': 'write_file', 'group': 'file:write', 'use': 'righaven_core.sandbox.tools:write_file_tool'},
            {'name': 'str_replace', 'group': 'file:write', 'use': 'righaven_core.sandbox.tools:str_replace_tool'},
        ])
        content['tool_groups'].append({'name': 'file:write'})
        path.write_text(yaml.safe_dump(content))
        self.bootstrap.initialize()
        migrated = yaml.safe_load(path.read_text())
        self.assertEqual(self.state.team()['engine'], 'deepseek')
        self.assertFalse(any(t['name'] in ('write_file', 'str_replace') for t in migrated['tools']))
        self.assertFalse(any(g['name'] == 'file:write' for g in migrated['tool_groups']))
        self.assertIn('Non ricopiare', migrated['lead_prompt_overlay']['append'])
        self.assertIn('sottocartelle', migrated['lead_prompt_overlay']['append'])

    def test_legacy_coordinator_and_provider_routes_apply_shared_profile(self):
        # A saved conversation using the old alias also follows the global choice.
        path = self.state.STATE / 'config.yaml'
        content = yaml.safe_load(path.read_text())
        content['models'].append({**content['models'][0], 'name': 'rh-deepseek'})
        path.write_text(yaml.safe_dump(content))
        with patch('righaven.deepseek.models', return_value=['deepseek-flash', 'deepseek-pro']):
            response = self.client.put('/harness/api/providers/deepseek', json={'api_key': 'test-key'})
            self.assertEqual(response.status_code, 200)
            response = self.client.put('/harness/api/coordinator', json={'model': 'deepseek-pro'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model'], 'deepseek-pro')
        self.assertTrue(all(p['model'] == 'deepseek-pro' for p in yaml.safe_load(path.read_text())['models']))
        self.assertTrue(all(s['model'] == 'deepseek-pro'
            for s in self.client.get('/harness/api/catalog').json()['effective_agents'].values()))

    def test_upgrade_adds_lesson_proposal_tool_without_replacing_profiles(self):
        path=self.state.STATE/'config.yaml'
        config=yaml.safe_load(path.read_text())
        config['tools']=[t for t in config['tools'] if t['name']!='harness_lessons']
        models=config['models']
        path.write_text(yaml.safe_dump(config))
        self.bootstrap.initialize()
        migrated=yaml.safe_load(path.read_text())
        self.assertEqual(migrated['models'],models)
        self.assertEqual(sum(t['name']=='harness_lessons' for t in migrated['tools']),1)
        self.bootstrap.initialize()
        self.assertEqual(sum(t['name']=='harness_lessons' for t in yaml.safe_load(path.read_text())['tools']),1)
