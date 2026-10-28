"""Verify Phase 2 (Community Gallery / RigHaven Hub) and Phase 3 (Dual Edition Cloud Portal & Multi-Tenant Vault)."""
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


class GalleryAndCloudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {
            'RIGHAVEN_STATE': str(Path(self.temp.name) / 'state'),
            'RIGHAVEN_WORKSPACE_ROOT': str(Path(self.temp.name) / 'user-data'),
            'RIGHAVEN_PASSWORD': 'test-righaven-password-at-least-16-chars',
            'RIGHAVEN_EDITION': 'cloud',
        })
        self.env_patch.start()
        from righaven import state, gallery, gallery_routes, cloud_portal, cloud_routes
        importlib.reload(state)
        importlib.reload(gallery)
        importlib.reload(gallery_routes)
        importlib.reload(cloud_portal)
        importlib.reload(cloud_routes)
        app = FastAPI()
        app.include_router(gallery_routes.router)
        app.include_router(cloud_routes.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        self.temp.cleanup()

    def test_gallery_catalog_contains_environments_37_cli_tools_and_skills_in_en_and_it(self):
        res_en = self.client.get('/api/v1/gallery/packs', headers={'Accept-Language': 'en'})
        self.assertEqual(res_en.status_code, 200)
        data = res_en.json()
        self.assertGreaterEqual(data['categories']['environment'], 5)
        self.assertGreaterEqual(data['categories']['cli-tool'], 37)
        self.assertGreaterEqual(data['categories']['skill'], 41)
        pack_ids = {p['id'] for p in data['packs']}
        for expected in ('env-architecture-modeling-rig', 'skill-typst', 'skill-c4-structurizr', 'skill-d2', 'skill-bpmn', 'skill-pandoc', 'skill-ffmpeg'):
            self.assertIn(expected, pack_ids)

        res_it = self.client.get('/api/v1/gallery/packs/env-architecture-modeling-rig', headers={'Accept-Language': 'it'})
        self.assertEqual(res_it.status_code, 200)
        self.assertEqual(res_it.json()['display_title'], 'Rig Architettura e Modellazione')

    def test_gallery_pack_activation_and_publish_with_schema_validation(self):
        ws = Path(self.temp.name) / 'workspace'
        ws.mkdir()
        act = self.client.post(
            '/api/v1/gallery/packs/env-architecture-modeling-rig/activate',
            json={'user_id': 'alice', 'workspace': str(ws)},
            headers={'Accept-Language': 'en'},
        )
        self.assertEqual(act.status_code, 200)
        self.assertTrue(act.json()['activated'])
        self.assertIn('structurizr', act.json()['injected_tools'])
        self.assertTrue((ws / '.righaven-project/gallery-packs.json').is_file())

        # Invalid pack rejected with 422
        bad = self.client.post('/api/v1/gallery/packs/publish', json={'id': 'bad'})
        self.assertEqual(bad.status_code, 422)

        # Valid custom pack published, starred, and forked
        custom_pack = {
            'id': 'skill-custom-scraper',
            'name': 'Custom Web Scraper Skill',
            'version': '1.0.0',
            'author': 'alice',
            'category': 'skill',
            'i18n': {
                'en': {'title': 'Custom Web Scraper', 'description': 'Scrapes structured data safely.'},
                'it': {'title': 'Scraper Web Personalizzato', 'description': 'Estrae dati strutturati in sicurezza.'},
            },
            'docker_dependencies': {
                'base_image': 'righaven-sandbox:0.1.0',
                'system_packages': [],
                'python_packages': ['beautifulsoup4'],
                'node_packages': [],
            },
            'cli_binaries': [
                {'name': 'playwright', 'executable': '/usr/local/bin/playwright-cli', 'safe_flags': ['test'], 'health_check': 'craft capabilities playwright'}
            ],
            'skill_prompt_template': 'Use playwright-cli in $RIGHAVEN_OUTPUT_DIR and verify reopen.',
            'verification_command': 'craft capabilities playwright',
            'security_policy': {
                'rootless': True,
                'network_access': False,
                'writable_paths': ['$RIGHAVEN_OUTPUT_DIR'],
                'read_only_mounts': ['/mnt/user-data'],
            },
        }
        pub = self.client.post('/api/v1/gallery/packs/publish', json=custom_pack)
        self.assertEqual(pub.status_code, 201)
        self.assertEqual(pub.json()['pack_id'], 'skill-custom-scraper')

        star = self.client.post('/api/v1/gallery/packs/skill-custom-scraper/star?user_id=bob')
        self.assertEqual(star.status_code, 200)
        self.assertEqual(star.json()['stars'], 1)

        fork = self.client.post('/api/v1/gallery/packs/skill-custom-scraper/fork', json={'author': 'bob'})
        self.assertEqual(fork.status_code, 201)
        self.assertEqual(fork.json()['pack']['author'], 'bob')

    def test_cloud_portal_multi_tenant_auth_workspace_vault_and_quotas(self):
        ed = self.client.get('/api/v1/cloud/edition')
        self.assertEqual(ed.status_code, 200)
        self.assertEqual(ed.json()['edition'], 'cloud')
        self.assertTrue(ed.json()['is_cloud'])

        # Sign up creates isolated tenant workspace /mnt/user-data/tenants/<user_id>
        signup = self.client.post('/api/v1/cloud/auth/signup', json={
            'username': 'marco_dev',
            'email': 'marco@example.com',
            'password': 'strong-password-123',
            'locale': 'it',
        })
        self.assertEqual(signup.status_code, 201)
        token = signup.json()['token']
        self.assertEqual(signup.json()['user']['workspace_path'], '/mnt/user-data/tenants/marco_dev')
        self.assertTrue((Path(self.temp.name) / 'user-data/tenants/marco_dev/.righaven-project').is_dir())

        # Login with username or email
        login = self.client.post('/api/v1/cloud/auth/login', json={
            'identifier': 'marco@example.com',
            'password': 'strong-password-123',
        })
        self.assertEqual(login.status_code, 200)

        # OAuth2 login
        oauth = self.client.post('/api/v1/cloud/auth/oauth/github', json={
            'username': 'gh_anna',
            'email': 'anna@github.example',
            'locale': 'en',
        })
        self.assertEqual(oauth.status_code, 200)
        self.assertEqual(oauth.json()['user']['workspace_path'], '/mnt/user-data/tenants/gh_anna')

        # Encrypted Vault never exposes raw API key
        headers = {'Authorization': f'Bearer {token}'}
        vault_put = self.client.put('/api/v1/cloud/vault/deepseek', json={'api_key': 'sk-secret-deepseek-9999'}, headers=headers)
        self.assertEqual(vault_put.status_code, 200)
        self.assertNotIn('sk-secret-deepseek-9999', json.dumps(vault_put.json()))
        self.assertTrue(vault_put.json()['providers']['deepseek']['configured'])

        # Resource Quotas tracking
        q = self.client.post('/api/v1/cloud/quotas/record', json={
            'sandbox_minutes': 12.5,
            'storage_bytes': 1048576,
            'tokens': 15000,
            'job_id': 'rh-job-0123456789ab',
        }, headers=headers)
        self.assertEqual(q.status_code, 200)
        self.assertEqual(q.json()['sandbox_minutes_used'], 12.5)
        self.assertEqual(q.json()['tokens_used'], 15000)


if __name__ == '__main__':
    unittest.main()
