"""Machine usage: who used which machine, how and how much."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import progress, state, usage_ledger


class UsageLedgerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        fixture = patch.object(state, 'STATE', self.root / 'state'); fixture.start(); self.addCleanup(fixture.stop)

    def workspace(self, user, thread):
        path = self.root / 'users' / user / 'threads' / thread / 'user-data'; path.mkdir(parents=True)
        return path

    def finish(self, workspace, job, role, profile, mode, cpu, phase='completed'):
        path = progress.create_job(workspace, job, 'workspace', 'claude', 'opus')
        progress.update(path, role_title=role, environment={'id': 'e' * 64, 'tools': ['d2'], 'profile': {'mode': mode, 'profile': profile}},
                        resources={'cpu_seconds': cpu, 'memory_peak_bytes': 1024 * cpu})
        progress.update(path, 'running_tool')
        progress.update(path, phase)
        progress.update(path, phase, 'Risorse rilasciate')  # repeated terminal updates keep one row

    def test_every_finished_assignment_is_recorded_once_with_its_machine(self):
        anna, bruno = self.workspace('anna', 'chat-1'), self.workspace('bruno', 'chat-2')
        self.assertEqual(usage_ledger.owner(anna), ('anna', 'chat-1'))
        self.finish(anna, 'rh-job-aaaaaaaaaaaa', 'Impaginatore', 'documenti', 'extended', 30)
        self.finish(anna, 'rh-job-bbbbbbbbbbbb', 'Revisore', 'documenti', 'reused', 10)
        self.finish(bruno, 'rh-job-cccccccccccc', 'Analista', '', 'none', 5, phase='failed')
        everyone = usage_ledger.report()
        self.assertEqual(everyone['totals']['jobs'], 3)
        machines = {m['name']: m for m in everyone['machines']}
        self.assertEqual((machines['documenti']['jobs'], machines['documenti']['reused'], machines['documenti']['extended']), (2, 1, 1))
        self.assertEqual(machines['documenti']['cpu_seconds'], 40)
        self.assertEqual(machines['dedicated']['jobs'], 1)
        self.assertEqual({u['name']: u['jobs'] for u in everyone['users']}, {'anna': 2, 'bruno': 1})
        self.assertEqual(everyone['jobs'][0]['tools'], ['d2'])
        own = usage_ledger.report('bruno')
        self.assertEqual((own['totals']['jobs'], own['users'], own['jobs'][0]['outcome']), (1, [], 'failed'))
        with self.assertRaises(ValueError):
            usage_ledger.report(days=0)

    def test_isolated_workers_do_not_write_the_ledger(self):
        anna = self.workspace('anna', 'chat-1')
        with patch.dict('os.environ', {'RIGHAVEN_ISOLATED_OUTPUT': '1'}):
            path = progress.create_job(anna, 'rh-job-dddddddddddd', 'workspace', 'claude', 'opus')
            progress.update(path, 'failed')
        self.assertEqual(usage_ledger.report()['totals']['jobs'], 0)


try:
    from righaven.usage_routes import router
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    router = None


@unittest.skipIf(router is None, 'Requires the pinned Gateway image')
class UsageRouteTests(UsageLedgerTests):
    def test_administrators_see_every_user_and_users_their_own(self):
        from types import SimpleNamespace
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.gateway.authz import AuthContext
        from righaven_core.runtime.user_context import set_current_user, reset_current_user
        self.finish(self.workspace('anna', 'chat-1'), 'rh-job-aaaaaaaaaaaa', 'Impaginatore', 'documenti', 'reused', 3)
        self.finish(self.workspace('bruno', 'chat-2'), 'rh-job-bbbbbbbbbbbb', 'Analista', '', 'none', 4)
        app = FastAPI(); app.include_router(router)

        @app.middleware('http')
        async def fixture_auth(request, call_next):
            name = request.headers.get('X-Test-User')
            user = SimpleNamespace(id=name, system_role='admin' if name == 'admin' else 'user')
            request.state.auth = AuthContext(user, ['threads:read']); request.state.user = user
            token = set_current_user(user)
            try:
                return await call_next(request)
            finally:
                reset_current_user(token)
        with TestClient(app) as client:
            admin = client.get('/api/harness/usage', headers={'X-Test-User': 'admin'}).json()
            self.assertEqual((admin['scope'], admin['totals']['jobs']), ('all', 2))
            own = client.get('/api/harness/usage?days=7', headers={'X-Test-User': 'anna'}).json()
            self.assertEqual((own['scope'], own['totals']['jobs'], own['jobs'][0]['user_id']), ('own', 1, 'anna'))
            self.assertEqual(client.get('/api/harness/usage?days=999', headers={'X-Test-User': 'anna'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
