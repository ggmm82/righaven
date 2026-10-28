"""Regression checks for CLI authentication, release wiring and tool onboarding."""
import importlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts.prepare_hostinger import prepare
from scripts.sync_catalog import sync
from righaven.login import login_command
from righaven.run_agent import command

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_gemini_manual_login_is_interactive_and_worker_can_read_shared_inputs(self):
        login = login_command('gemini')
        self.assertEqual(login, ['python3', '/opt/righaven-worker/antigravity_cli.py', '--login'])
        self.assertNotIn('--prompt', login)
        self.assertNotIn('--output-format', login)
        args = command('gemini', 'chosen-model', 'Task', '/tmp/final')
        self.assertEqual(args[args.index('--add-dir') + 1], '/mnt/user-data')
        self.assertEqual(args[args.index('--model') + 1], 'chosen-model')
        self.assertIn('--input-format', args)
        self.assertEqual(args[0], 'agy')
        self.assertIn('summary', json.loads(args[args.index('--json-schema') + 1])['required'])
        self.assertEqual(login_command('codex'), ['codex', 'login', '--device-auth'])

    def test_hostinger_release_checks_every_image_before_replacing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'compose.yaml'
            target.write_text('previous working release')
            commit = 'a' * 40
            def unavailable(image):
                if '-frontend:' in image:
                    raise RuntimeError('Image not published')
            with self.assertRaises(RuntimeError):
                prepare(commit, target, inspect=unavailable)
            self.assertEqual(target.read_text(), 'previous working release')
            verified = []
            prepare(commit, target, inspect=verified.append)
            result = yaml.safe_load(target.read_text())
            self.assertEqual(len(verified), 3)
            for service in ('gateway', 'frontend'):
                self.assertTrue(result['services'][service]['image'].endswith(':sha-' + commit))
            self.assertTrue(result['services']['gateway']['environment']['RIGHAVEN_SANDBOX_IMAGE'].endswith(':sha-' + commit))
            self.assertNotIn('sandbox-image', result['services'])
            self.assertEqual(result['services']['gateway']['environment']['DOCKER_HOST'], 'unix:///runtime/docker.sock')
            self.assertFalse(any('docker.sock' in str(volume) for service in result['services'].values()
                                 for volume in service.get('volumes', [])))
            self.assertNotIn('ports', result['services']['gateway'])
            self.assertIn('${TRAEFIK_HOST', result['services']['frontend']['environment']['BETTER_AUTH_URL'])
            with self.assertRaises(ValueError):
                prepare('latest', target, inspect=verified.append)

    def test_new_tool_propagates_without_another_model_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('config', 'righaven', 'skills/custom'):
                (root / folder).mkdir(parents=True, exist_ok=True)
            content = yaml.safe_load((ROOT / 'config/righaven.yaml').read_text())
            profiles = content['models']
            (root / 'config/righaven.yaml').write_text(yaml.safe_dump(content))
            lock = json.loads((ROOT / 'versions.lock.json').read_text())
            new_tool = {**lock['applications'][0], 'id': 'newcraft', 'role': 'Nuovo strumento'}
            lock['applications'].append(new_tool)
            (root / 'versions.lock.json').write_text(json.dumps(lock))
            for app in lock['applications'][:-1]:
                skill = root / 'skills/custom' / ('skill-' + app['id'])
                skill.mkdir()
                (skill / 'SKILL.md').write_text('Existing skill')
            with self.assertRaisesRegex(ValueError, 'newcraft'):
                sync(root)
            skill = root / 'skills/custom/skill-newcraft'
            skill.mkdir()
            (skill / 'SKILL.md').write_text('New tool procedure')
            sync(root)
            changed = yaml.safe_load((root / 'config/righaven.yaml').read_text())
            self.assertEqual(changed['models'], profiles)
            self.assertEqual(changed['subagents']['custom_agents']['newcraft']['model'], 'inherit')
            self.assertIn('newcraft per Nuovo strumento', changed['lead_prompt_overlay']['append'])
            self.assertEqual((root / 'righaven/righaven.yaml').read_bytes(), (root / 'config/righaven.yaml').read_bytes())
            self.assertEqual((root / 'righaven/versions.lock.json').read_bytes(), (root / 'versions.lock.json').read_bytes())
            once = (root / 'config/righaven.yaml').read_bytes()
            sync(root)
            self.assertEqual(once, (root / 'config/righaven.yaml').read_bytes())

    def test_existing_installation_adds_new_specialist_preserving_preferences(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'RIGHAVEN_STATE': directory, 'RIGHAVEN_PASSWORD': 'test-install-password-long-enough'}):
            from righaven import state, bootstrap
            importlib.reload(state)
            importlib.reload(bootstrap)
            bootstrap.initialize()
            state.update_agent('wordcraft', {'engine': 'inherit', 'instructions': 'Stile sobrio', 'enabled': False})
            template = Path(directory) / 'new-template'
            shutil.copytree(ROOT / 'righaven', template, ignore=shutil.ignore_patterns('__pycache__'))
            config = yaml.safe_load((template / 'righaven.yaml').read_text())
            config['subagents']['custom_agents']['newcraft'] = {
                **config['subagents']['custom_agents']['wordcraft'], 'skills': ['skill-workspace', 'skill-newcraft']}
            (template / 'righaven.yaml').write_text(yaml.safe_dump(config))
            applications = state.applications() + [{'id': 'newcraft'}]
            with patch.object(state, 'applications', return_value=applications), patch.object(bootstrap, 'ROOT', template):
                bootstrap.initialize()
                new = state.effective_agent('newcraft')
                self.assertEqual((new['engine'], new['model']), ('codex', 'gpt-6.1-sol'))
                self.assertIn('skill-newcraft', new['skills'])
                from righaven.router import AgentConfig
                values = AgentConfig(skills=state.available_skills()).model_dump()
                updated = state.update_agent('newcraft', values)
                self.assertEqual(set(updated['skills']), set(state.available_skills()))
            old = state.catalog()['wordcraft']
            self.assertFalse(old['enabled'])
            self.assertEqual(old['instructions'], 'Stile sobrio')
            self.assertIn('newcraft', yaml.safe_load((Path(directory) / 'config.yaml').read_text())['subagents']['custom_agents'])

    def test_upgrade_adds_project_tool_and_team_instructions_without_changing_model(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'RIGHAVEN_STATE': directory, 'RIGHAVEN_PASSWORD': 'test-install-password-long-enough'}):
            from righaven import state, bootstrap
            importlib.reload(state)
            importlib.reload(bootstrap)
            bootstrap.initialize()
            path = Path(directory) / 'config.yaml'
            old = yaml.safe_load(path.read_text())
            old['tools'] = [t for t in old['tools'] if t['name'] != 'harness_plan']
            old['lead_prompt_overlay']['append'] = 'Sei la RigHaven Harness. Vecchia regia.'
            old['models'][0]['model'] = 'user-selected-model'
            path.write_text(yaml.safe_dump(old))
            bootstrap.initialize()
            upgraded = yaml.safe_load(path.read_text())
            self.assertIn('harness_plan', [t['name'] for t in upgraded['tools']])
            self.assertIn('animated_video', upgraded['lead_prompt_overlay']['append'])
            self.assertEqual(upgraded['models'][0]['model'], 'user-selected-model')


if __name__ == '__main__':
    unittest.main()
