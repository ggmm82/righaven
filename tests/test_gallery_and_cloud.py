"""Shared identity, immutable publishing and native activation boundaries."""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

class GalleryAndCloudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'RIGHAVEN_STATE': self.temp.name, 'RIGHAVEN_EDITION': 'cloud'})
        self.env.start(); self.addCleanup(self.env.stop)
        from righaven import state, gallery, gallery_routes, cloud_routes
        importlib.reload(state)
        self.gallery = gallery
        app = FastAPI()
        @app.middleware('http')
        async def identity(request, call_next):
            if request.headers.get('x-test-anonymous') != '1':
                request.state.user = SimpleNamespace(id=request.headers.get('x-test-user', 'alice'),
                    email='alice@example.test', system_role='user')
            return await call_next(request)
        app.include_router(gallery_routes.router)
        app.include_router(cloud_routes.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def pack(self):
        value = dict(self.gallery.get_pack('skill-d2'))
        value.update(id='skill-custom-diagram', author='spoofed-author', verified=True, version='1.0.0')
        return value

    def test_authentication_and_owner_cannot_be_supplied_in_body(self):
        self.assertEqual(self.client.get('/api/v1/gallery/packs', headers={'x-test-anonymous':'1'}).status_code, 401)
        response=self.client.post('/api/v1/gallery/packs/skill-d2/activate',
                                 json={'user_id':'victim','workspace':'/etc'})
        self.assertEqual(response.status_code,422)

    def test_native_activation_precedes_success_and_uses_session_owner(self):
        with patch('righaven.pack_activation.install', new_callable=AsyncMock) as install:
            install.return_value={'native_name':'pack-native','sha256':'fixture','tools':['d2']}
            response=self.client.post('/api/v1/gallery/packs/skill-d2/activate',json={})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(install.call_args.args[1],'alice')
            self.assertIn('skill-d2',self.gallery.active_packs_for('alice'))
            self.assertEqual(self.gallery.active_packs_for('victim'),[])
        with patch('righaven.pack_activation.install',new_callable=AsyncMock,side_effect=ValueError('disabled')):
            response=self.client.post('/api/v1/gallery/packs/skill-typst/activate',json={})
            self.assertEqual(response.status_code,422)
            self.assertNotIn('skill-typst',self.gallery.active_packs_for('alice'))

    def test_publishing_requires_ownership_and_immutable_version(self):
        pack=self.pack()
        result=self.client.post('/api/v1/gallery/packs/publish',json=pack)
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(result.json()['pack']['author'],'alice')
        self.assertFalse(result.json()['pack']['verified'])
        pack['skill_prompt_template']='Changed same version'
        self.assertEqual(self.client.post('/api/v1/gallery/packs/publish',json=pack).status_code,422)
        pack['version']='2.0.0'
        self.assertEqual(self.client.post('/api/v1/gallery/packs/publish',json=pack,headers={'x-test-user':'bob'}).status_code,422)
        self.assertEqual(self.client.post('/api/v1/gallery/packs/publish',json=pack).status_code,201)
        self.assertTrue((Path(self.temp.name)/'gallery-versions/skill-custom-diagram/1.0.0.json').is_file())

    def test_cloud_uses_native_identity_and_rejects_unsafe_preview_endpoints(self):
        self.assertEqual(self.client.get('/api/v1/cloud/me').json()['user']['id'],'alice')
        for endpoint,body in [('auth/oauth/google',{'username':'victim','email':'victim@example.test'}),
                              ('auth/recover',{'email':'victim@example.test','new_password':'attacker-password'}),
                              ('onboarding',{'user_id':'victim'})]:
            self.assertEqual(self.client.post('/api/v1/cloud/'+endpoint,json=body).status_code,410)
        capabilities = self.client.get('/api/v1/cloud/edition').json()['capabilities']
        self.assertTrue(capabilities['job_admission_limits'])
        self.assertFalse(capabilities['shared_organizations'])
