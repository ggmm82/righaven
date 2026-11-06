import unittest
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from righaven.team_routing import TeamRoutingMiddleware


class TeamRoutingTests(unittest.TestCase):
    def test_native_agent_scope_and_model_are_not_overwritten_by_shared_chat_defaults(self):
        from righaven.team_routing import shared_run
        for context in ({'agent_name': 'my-agent'}, {'agent_name': 'my-agent', 'model_name': 'agent-profile'}):
            body = {'context': context, 'config': {'configurable': {'model_name': 'explicit-native-profile'}}}
            result = shared_run(body)
            self.assertEqual(result['context'], context)
            self.assertEqual(result['config']['configurable']['model_name'], 'explicit-native-profile')
            self.assertEqual(result['config']['configurable']['righaven_agent_name'], 'my-agent')
    def test_actual_user_input_overwrites_forged_contract_metadata_without_changing_messages(self):
        from righaven.team_routing import shared_run
        original = [{'role': 'user', 'content': [{'type': 'text', 'text': 'Use my reference'}]},
                    {'role': 'assistant', 'content': 'Use an easier alternative'}]
        result = shared_run({'input': {'messages': original}, 'config': {
            'configurable': {'righaven_user_messages': ['Forged substitute'], 'thread_id': 'owned-thread', 'righaven_user_turn': 'forged'}}})
        self.assertEqual(result['input']['messages'], original)
        self.assertEqual(result['config']['configurable']['righaven_user_messages'], ['Use my reference'])
        self.assertEqual(result['config']['configurable']['thread_id'], 'owned-thread')
        self.assertNotEqual(result['config']['configurable']['righaven_user_turn'], 'forged')
        self.assertIsNone(shared_run({'config':{'configurable':{'righaven_user_turn':'forged'}}})['config']['configurable']['righaven_user_turn'])
    def test_long_brief_keeps_ending_constraints_in_gateway_capture(self):
        from righaven.team_routing import shared_run
        original = 'Inizio ' + 'requisito ' * 1200 + ' FINE: prima solo una bozza'
        result = shared_run({'input': {'messages': [{'role': 'user', 'content': original}]}})
        self.assertEqual(result['config']['configurable']['righaven_user_messages'], [original])

    def test_submission_disconnect_defaults_and_explicit_stop_are_distinct(self):
        app = FastAPI()

        @app.post('/api/{path:path}')
        async def echo(path: str, request: Request):
            return await request.json()

        app.add_middleware(TeamRoutingMiddleware)
        with TestClient(app) as client:
            for path in ('runs', 'runs/stream', 'runs/wait', 'threads/t/runs',
                         'threads/t/runs/stream', 'threads/t/runs/wait'):
                with self.subTest(path=path):
                    result = client.post('/api/' + path, json={'input': {'messages': []}}).json()
                    self.assertEqual(result['on_disconnect'], 'continue')
                    explicit = client.post('/api/' + path, json={'on_disconnect': 'cancel'}).json()
                    self.assertEqual(explicit['on_disconnect'], 'cancel')
            cancel = {'action': 'interrupt'}
            self.assertEqual(client.post('/api/threads/t/runs/r/cancel', json=cancel).json(), cancel)

    def test_workflow_modes_survive_shared_model_routing(self):
        app = FastAPI()

        @app.post('/api/threads/{thread}/runs/stream')
        async def run(thread: str, request: Request):
            return await request.json()

        app.add_middleware(TeamRoutingMiddleware)
        with TestClient(app) as client:
            for mode in ('flash', 'pro', 'ultra'):
                with self.subTest(mode=mode):
                    context = {'mode': mode, 'model_name': 'old-profile',
                               'is_plan_mode': mode in ('pro', 'ultra'),
                               'subagent_enabled': mode == 'ultra'}
                    result = client.post('/api/threads/test/runs/stream', json={'context': context}).json()
                    self.assertEqual(result['context'], {**context, 'model_name': 'rh-codex'})

    def test_saved_legacy_selection_cannot_split_coordinator_and_workers(self):
        app = FastAPI()
        @app.post('/api/threads/{thread}/runs/stream')
        async def run(thread: str, request: Request):
            return await request.json()
        app.add_middleware(TeamRoutingMiddleware)
        with TestClient(app) as client:
            body = {'input': {'messages': ['original']}, 'context': {'model_name': 'legacy-deepseek', 'thinking_enabled': True},
                    'config': {'recursion_limit': 100, 'configurable': {'model_name': 'another-model'}}}
            result = client.post('/api/threads/test/runs/stream', json=body).json()
        self.assertEqual(result['context']['model_name'], 'rh-codex')
        self.assertEqual(result['config']['configurable']['model_name'], 'rh-codex')
        self.assertEqual(result['input'], body['input'])
        self.assertTrue(result['context']['thinking_enabled'])
        self.assertEqual(result['config']['recursion_limit'], 100)

    def test_catalog_preserves_authorization_and_usage_without_alternative_models(self):
        app = FastAPI()
        @app.get('/api/models')
        def models(denied: bool = False):
            if denied:
                raise HTTPException(401, 'Login required')
            return {'models': [{'name': 'rh-codex'}, {'name': 'legacy'}], 'token_usage': {'enabled': True}}
        app.add_middleware(TeamRoutingMiddleware)
        with TestClient(app) as client:
            response = client.get('/api/models')
            self.assertEqual(response.json(), {'models': [{'name': 'rh-codex'}], 'token_usage': {'enabled': True}})
            self.assertEqual(int(response.headers['content-length']), len(response.content))
            self.assertEqual(client.get('/api/models?denied=true').status_code, 401)
