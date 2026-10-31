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

    def test_tokens_from_every_provider_shape_become_costs_with_admin_prices(self):
        self.assertEqual(progress.token_counts({'inputTokens': 1000, 'cachedInputTokens': 400, 'outputTokens': 50, 'reasoningOutputTokens': 20, 'totalTokens': 1050}),
                         {'input': 1000, 'cached_input': 400, 'output': 50, 'reasoning': 20})
        self.assertEqual(progress.token_counts({'prompt_tokens': 300, 'completion_tokens': 30, 'prompt_cache_hit_tokens': 100}),
                         {'input': 300, 'cached_input': 100, 'output': 30, 'reasoning': 0})
        self.assertEqual(progress.token_counts({'input_tokens': 10, 'cache_read_input_tokens': 90, 'cache_creation_input_tokens': 5, 'output_tokens': 7}),
                         {'input': 105, 'cached_input': 90, 'output': 7, 'reasoning': 0})
        self.assertIsNone(progress.token_counts({'total_tokens': 0}))
        from righaven import model_prices
        model_prices.save({'currency': 'EUR', 'models': {'opus': {'input': 10, 'cached_input': 1, 'output': 50}}})
        anna = self.workspace('anna', 'chat-1')
        path = progress.create_job(anna, 'rh-job-aaaaaaaaaaaa', 'workspace', 'claude', 'opus')
        reporter = progress.Reporter.__new__(progress.Reporter); reporter.path = path
        reporter.tokens({'prompt_tokens': 600_000, 'completion_tokens': 10_000, 'prompt_tokens_details': {'cached_tokens': 100_000}})
        reporter.tokens({'prompt_tokens': 400_000, 'completion_tokens': 10_000})  # per-call usage adds up
        self.assertEqual(progress.public_status(progress.read_status(path))['tokens'], {'input': 1_000_000, 'cached_input': 100_000, 'output': 20_000, 'reasoning': 0})
        progress.update(path, 'completed')
        report = usage_ledger.report()
        # 900k uncached x 10 + 100k cached x 1 + 20k output x 50, per million tokens.
        self.assertEqual(report['jobs'][0]['cost'], 10.1)
        self.assertEqual((report['currency'], report['totals']['cost'], report['totals']['input_tokens']), ('EUR', 10.1, 1_000_000))
        self.assertEqual({m['name']: m['cost'] for m in report['models']}, {'opus': 10.1})
        with self.assertRaises(ValueError):
            model_prices.save({'currency': 'EUR', 'models': {'opus': {'input': -1}}})

    def test_quota_exhaustion_raises_an_alert_and_old_ledgers_gain_the_new_columns(self):
        import sqlite3
        database = state.STATE / 'usage-ledger.sqlite3'; database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as conn:
            conn.execute('CREATE TABLE jobs (job_id TEXT PRIMARY KEY, user_id TEXT, thread_id TEXT, started_at TEXT, finished_at TEXT, '
                         'duration_seconds REAL, role TEXT, agent TEXT, engine TEXT, model TEXT, profile TEXT, mode TEXT, environment_id TEXT, '
                         'tools TEXT, cpu_seconds REAL, memory_peak_bytes INTEGER, outcome TEXT)')
        anna = self.workspace('anna', 'chat-1')
        path = progress.create_job(anna, 'rh-job-aaaaaaaaaaaa', 'workspace', 'codex', 'gpt-test')
        progress.update(path, 'failed', 'Quota esaurita', error_code='provider_quota')
        report = usage_ledger.report()
        self.assertEqual([(a['engine'], a['jobs'], a['users']) for a in report['quota_alerts']], [('codex', 1, 1)])
        self.assertIsNone(report['jobs'][0]['cost'])
        self.assertEqual(usage_ledger.report('bruno')['quota_alerts'], [])

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
            prices = {'currency': 'USD', 'models': {'opus': {'input': 15, 'output': 75}}}
            self.assertEqual(client.put('/api/harness/usage/prices', json=prices, headers={'X-Test-User': 'anna'}).status_code, 403)
            saved = client.put('/api/harness/usage/prices', json=prices, headers={'X-Test-User': 'admin'}).json()
            self.assertEqual(saved['models']['opus'], {'input': 15.0, 'cached_input': 15.0, 'output': 75.0})
            read = client.get('/api/harness/usage/prices', headers={'X-Test-User': 'anna'}).json()
            self.assertEqual((read['currency'], read['can_manage']), ('USD', False))


if __name__ == '__main__':
    unittest.main()
