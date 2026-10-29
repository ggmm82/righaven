"""Exercise real LangChain tool wrappers in the pinned Gateway image."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from righaven.tools import harness_delegate, harness_plan, harness_lessons
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    harness_delegate = None


@unittest.skipIf(harness_delegate is None, 'Requires the pinned Gateway tool runtime')
class AdaptiveToolTests(unittest.TestCase):
    def test_learning_pass_is_bounded_project_scoped_and_respects_stop(self):
        from langchain_core.messages import AIMessage
        from langgraph.runtime import Runtime as GraphRuntime
        from righaven.completion_middleware import ProjectCompletionMiddleware
        middleware=ProjectCompletionMiddleware()
        runtime=GraphRuntime(context={'user_id':'owner'})
        state={**middleware.before_agent({},runtime),'harness_production_started':True,'messages':[AIMessage('Result ready')]}
        with tempfile.TemporaryDirectory() as directory, \
                patch('righaven.completion_middleware.workspace_for',return_value=Path(directory)), \
                patch('righaven.completion_middleware.read_project',return_value={'status':'ready'}), \
                patch('righaven.completion_middleware.learning_sources',return_value=[{'id':'a'*64}]) as pending:
            result=middleware.after_model(state,runtime)
            self.assertEqual(result['jump_to'],'model')
            self.assertIn('current_project_only=true',result['harness_completion_reminder'])
            self.assertIn('non inventare prove',result['harness_completion_reminder'])
            state.update(result)
            self.assertNotIn('jump_to',middleware.after_model(state,runtime))
            self.assertEqual(pending.call_count,1)
            state['harness_learning_nudged']=False
            runtime.context['stop_reason']='budget'
            self.assertNotIn('jump_to',middleware.after_model(state,runtime))
            runtime.context.pop('stop_reason')
            with patch('righaven.completion_middleware.read_project',return_value={'status':'review','user_control':{'paused':True}}):
                self.assertNotIn('jump_to',middleware.after_model(state,runtime))
            self.assertEqual(pending.call_count,1)

    def test_native_completion_guard_resumes_incomplete_production_without_polluting_messages(self):
        from langchain_core.messages import AIMessage, HumanMessage
        from langgraph.runtime import Runtime as GraphRuntime
        from righaven.completion_middleware import ProjectCompletionMiddleware
        from righaven.projects import create_plan, read_project
        middleware = ProjectCompletionMiddleware()
        runtime = GraphRuntime(context={'user_id': 'owner'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_plan(root, 'Finish the product', [], next_action='Correct the observed defect', status='review')
            state = {**middleware.before_agent({}, runtime), 'messages': [HumanMessage('Finish the product'),
                AIMessage('', tool_calls=[{'id': 'delegate', 'name': 'harness_delegate', 'args': {'purpose': 'preview'}}])]}
            state.update(middleware.after_model(state, runtime))
            state['messages'].append(AIMessage('Here is an unfinished sample.'))
            with patch('righaven.completion_middleware.workspace_for', return_value=root):
                result = middleware.after_model(state, runtime)
                self.assertEqual(result['jump_to'], 'model')
                self.assertNotIn('messages', result)
                state.update(result)
                class Request:
                    def __init__(self): self.state=state; self.messages=list(state['messages'])
                    def override(self, **kwargs): return SimpleNamespace(**kwargs)
                request = Request()
                augmented = middleware.augmented(request)
                self.assertEqual(len(request.messages), len(state['messages']))
                self.assertEqual(len(augmented.messages), len(request.messages)+1)
                self.assertIn('Correct the observed defect', augmented.messages[-1].content)
                no_progress = middleware.after_model(state, runtime)
                self.assertNotIn('jump_to', no_progress)
                state['harness_work_generation'] += 1
                state.update(middleware.after_model(state, runtime))
                self.assertEqual(state['harness_completion_nudges'], 2)
                capped = middleware.after_model(state, runtime)
                self.assertNotIn('jump_to', capped)
                self.assertEqual(read_project(root)['attention']['code'], 'incomplete_objective')
                runtime.context['stop_reason']='loop_capped'
                self.assertNotIn('jump_to', middleware.after_model({**state,'harness_completion_nudges':0},runtime))
            # Explain-only invocations do not inherit an old production flag.
            fresh = {**middleware.before_agent(state, runtime), 'messages': state['messages']}
            self.assertFalse(fresh['harness_production_started'])

    def test_completion_guard_runs_inside_native_compiled_agent_graph(self):
        from langchain.agents import create_agent
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from langchain_core.tools import tool
        from righaven.completion_middleware import ProjectCompletionMiddleware
        from righaven.projects import create_plan, read_project
        class Model(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs): return self
        @tool
        def harness_delegate(purpose: str) -> str:
            """Declared fixture: record that the sample is not the final product."""
            return '{"ok":true,"decision":"needs_revision"}'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            create_plan(root,'Complete product',[],status='review',next_action='Finish the result')
            model=Model(responses=[AIMessage('',tool_calls=[{'name':'harness_delegate','id':'fixture','args':{'purpose':'preview'}}]),
                AIMessage('Unfinished draft'),AIMessage('Still unfinished'),AIMessage('Cannot finish')])
            agent=create_agent(model,tools=[harness_delegate],middleware=[ProjectCompletionMiddleware()])
            with patch('righaven.completion_middleware.workspace_for',return_value=root):
                result=agent.invoke({'messages':[HumanMessage('Complete the product')]})
            self.assertEqual(result['harness_completion_nudges'],1)
            self.assertFalse(any(isinstance(m,SystemMessage) for m in result['messages']))
            self.assertEqual(read_project(root)['attention']['code'],'incomplete_objective')

    def test_native_middleware_records_model_and_tool_failures_without_prompts(self):
        import asyncio
        from righaven.audit_log import page
        from langgraph.runtime import Runtime as GraphRuntime
        from righaven_core.agents.middlewares.configured_extensions import load_configured_extension_middlewares
        config=SimpleNamespace(extensions=SimpleNamespace(middlewares=['righaven.audit_middleware:ConversationAuditMiddleware']))
        middleware,=load_configured_extension_middlewares(config)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=GraphRuntime(context={'user_id':'owner'})
            config={'configurable':{'thread_id':'thread','righaven_user_turn':'turn-fixture',
                'righaven_user_messages':['PRIVATE BRIEF must not be stored']}}
            request=SimpleNamespace(runtime=runtime,tool_call={'name':'read_file','id':'call-fixture'})
            with patch('righaven.audit_middleware.workspace_for',return_value=root), patch('langgraph.config.get_config',return_value=config):
                middleware.before_agent({},runtime)
                middleware.wrap_tool_call(request,lambda _:SimpleNamespace(content='Error: access denied'))
                middleware.wrap_model_call(request,lambda _:SimpleNamespace(content='PRIVATE RESPONSE'))
                async def cancelled(_):raise asyncio.CancelledError()
                with self.assertRaises(asyncio.CancelledError):asyncio.run(middleware.awrap_model_call(request,cancelled))
            rows=page(root)['events']
            self.assertEqual(sum(r['actor']=='Utente' for r in rows),1)
            self.assertTrue(any(r['status']=='failed' for r in rows))
            self.assertTrue(any(r['status']=='interrupted' for r in rows))
            self.assertNotIn('PRIVATE',json.dumps(rows))

    def test_hidden_project_context_uses_a_scoped_hash_checked_reader(self):
        from righaven.project_skills import scoped_file
        from righaven.tools import harness_read_context
        from righaven_core.sandbox.tools import _validate_resolved_user_data_path
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('workspace','uploads','outputs'):(root/name).mkdir()
            reference=scoped_file(root,'control-results/actual.json','{"state":"full"}')
            local=root/'.righaven-project/control-results/actual.json'
            thread_data={name+'_path':str(root/name) for name in ('workspace','uploads','outputs')}
            with self.assertRaises(PermissionError):_validate_resolved_user_data_path(local,thread_data)
            with patch('righaven.tools.workspace_for',return_value=root):
                value=json.loads(harness_read_context.func(runtime=SimpleNamespace(),path=reference['path'],sha256=reference['sha256']))
                self.assertEqual(json.loads(value['content']),{'state':'full'})
            self.assertNotIn('runtime',harness_read_context.tool_call_schema.model_json_schema()['properties'])

    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        fixture = patch('righaven.tools.experience_root', return_value=Path(directory.name) / 'library')
        fixture.start(); self.addCleanup(fixture.stop)
        # These tests isolate the tool/project boundary. Native storage and its
        # Agent/user semantics are exercised by check_native_capabilities.py.
        from righaven.capability_policy import policy_from_names
        from righaven.state import applications
        self.capabilities = policy_from_names({'skill-' + a['id'] for a in applications()}, source='fixture')
        fixture = patch('righaven.capability_policy.runtime_policy', return_value=self.capabilities)
        fixture.start(); self.addCleanup(fixture.stop)

    def test_planner_requires_an_explicit_reason_for_an_empty_capability_assignment(self):
        from test_project_skills import role
        spec=role();spec.pop('capability_rationale')
        runtime=SimpleNamespace(state={'messages':[SimpleNamespace(type='human',content='Create a text proposal')]})
        with tempfile.TemporaryDirectory() as directory, patch('righaven.tools.workspace_for',return_value=Path(directory)):
            with self.assertRaisesRegex(ValueError,'capability_rationale'):
                harness_plan.func(runtime=runtime,brief='Create a text proposal',roles_json=json.dumps([spec]))
            spec['capability_rationale']='Base Python is sufficient for a plain text proposal and checking its content.'
            result=json.loads(harness_plan.func(runtime=runtime,brief='Create a text proposal',roles_json=json.dumps([spec])))
            self.assertTrue(result['project'])

    def test_planner_cannot_assign_a_native_disabled_tool_to_a_new_role(self):
        from test_project_skills import role
        spec = role(); spec['tools'] = ['blender']
        scoped = {**self.capabilities, 'allowed': ['freecad'], 'blocked': ['blender']}
        runtime = SimpleNamespace(state={'messages': []})
        with tempfile.TemporaryDirectory() as folder, \
             patch('righaven.tools.workspace_for', return_value=Path(folder)), \
             patch('righaven.capability_policy.runtime_policy', return_value=scoped):
            with self.assertRaisesRegex(ValueError, 'disabilitato'):
                harness_plan.func(runtime=runtime, brief='Only native enabled tools', roles_json=json.dumps([spec]))

    def test_disabled_tool_does_not_persist_a_premature_blocked_plan(self):
        from righaven.projects import read_project
        scoped = {**self.capabilities, 'allowed': ['freecad'], 'blocked': ['blender']}
        runtime = SimpleNamespace(state={'messages': []})
        with tempfile.TemporaryDirectory() as folder, \
             patch('righaven.tools.workspace_for', return_value=Path(folder)), \
             patch('righaven.capability_policy.runtime_policy', return_value=scoped):
            with self.assertRaisesRegex(ValueError, 'scelta dell’utente'):
                harness_plan.func(runtime=runtime, brief='Editable 3D scene', status='blocked',
                    strategy_json=json.dumps({'state':'needs_user','method':'Blender',
                        'reason':'Disabled app','stop_reason':'capability_limit',
                        'user_action':'Enable Blender','alternatives':[]}))
            self.assertFalse(read_project(Path(folder)))

    def test_failed_sample_replans_and_new_method_reaches_worker(self):
        from righaven.projects import read_project
        from righaven.project_skills import read_document
        from righaven.run_agent import verify_project_context
        from test_project_skills import role
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / 'sample-review.json'; proof.write_text('{"defect":"observed"}')
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request',
                content='Create the complete result; choose the method yourself')]})
            failed = {'ok': True, 'quality_review': {'status': 'needs_revision', 'product_path': str(proof)},
                      'handoff': {'output_files': [str(proof)], 'checks': []}}
            with patch('righaven.tools.workspace_for', return_value=root), \
                 patch('righaven.state.team', return_value={'engine': 'codex', 'model': 'shared-fixture'}), \
                 patch('righaven.tools.delegate', return_value=json.dumps(failed)) as worker:
                harness_plan.func(runtime=runtime, brief='Complete product', roles_json=json.dumps([role()]),
                    outcome_json=json.dumps({'result': 'Complete product', 'format': 'Editable document',
                        'assumptions': ['Method chosen by the team']}))
                harness_delegate.func(agent='workspace', role_id='design', task='Review sample', purpose='review', runtime=runtime)
                response = json.loads(harness_plan.func(runtime=runtime, status='blocked'))['project']
                self.assertEqual(response['status'], 'review')
                self.assertEqual(response['method_recovery']['code'], 'method_selection_required')
                strategy = {'method': 'Different construction', 'reason': 'Addresses the observed limitation', 'state': 'selected',
                    'alternatives': [{'method': 'Prior construction', 'reason': 'Sample insufficient', 'tools': [],
                                      'status': 'tested', 'evidence_paths': ['/mnt/user-data/sample-review.json']}]}
                harness_plan.func(runtime=runtime, status='working', strategy_json=json.dumps(strategy))
                current = read_project(root)
                self.assertEqual(current['strategy']['request_hash'], current['acceptance']['hash'])
                worker.return_value = json.dumps({'ok': True})
                harness_delegate.func(agent='workspace', role_id='design', task='Try the new method', runtime=runtime)
                self.assertIn('Scelte provvisorie', worker.call_args.args[1])
                compiled = worker.call_args.kwargs['role']
                memory = json.loads(read_document(root, compiled['memory']))
                self.assertEqual(memory['method_selection'], current['strategy']['record'])
                verify_project_context({'role': compiled}, root)
                saved = root / Path(memory['method_selection']['path']).relative_to('/mnt/user-data')
                saved.write_text('Changed method after compilation')
                with self.assertRaisesRegex(ValueError, 'modificato'):
                    verify_project_context({'role': compiled}, root)

    def test_changed_owner_direction_is_returned_when_the_worker_finishes(self):
        from righaven.projects import set_user_direction
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request', content='Create an illustration')]})
            def work(*args, **kwargs):
                set_user_direction(root, 'vector', 'Voglio modificare i tracciati')
                return json.dumps({'ok': True})
            with patch('righaven.tools.workspace_for', return_value=root), \
                 patch('righaven.state.team', return_value={'engine': 'codex', 'model': 'fixture'}), \
                 patch('righaven.tools.delegate', side_effect=work):
                harness_plan.func(runtime=runtime, brief='Illustration', outcome_json=json.dumps({'result':'Illustration','format':'Editable source'}))
                result = json.loads(harness_delegate.func(agent='vectorcraft', task='Create', runtime=runtime))
                self.assertEqual(result['user_direction']['visual_approach'], 'vector')
                self.assertIn('ripianifica', result['direction_changed'])
                self.assertFalse(result['generation_capabilities']['native_images']['allowed_by_user'])

    def test_contract_uses_gateway_user_input_instead_of_synthetic_agent_message(self):
        from righaven.projects import read_project
        with tempfile.TemporaryDirectory() as directory:
            runtime = SimpleNamespace(context={'is_subagent': True}, config={'configurable': {'righaven_user_messages': ['Actual user reference']}},
                state={'messages': [SimpleNamespace(type='human', id='synthetic', content='An easier substitute requested by planner')]})
            with patch('righaven.tools.workspace_for', return_value=Path(directory)):
                harness_plan.func(runtime=runtime, brief='Coordinator interpretation')
                self.assertEqual(read_project(Path(directory))['acceptance']['user_requests'], ['Actual user reference'])

    def test_dynamic_role_reaches_worker_with_original_brief_and_shared_profile(self):
        from righaven.project_skills import load_compiled, read_document
        from righaven.projects import read_project
        from test_project_skills import role
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = 'Problema nuovo: ' + 'vincolo specifico ' * 600 + ' Fine: iniziare solo con una proposta.'
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request', content=original)]})
            with patch('righaven.tools.workspace_for', return_value=root), \
                 patch('righaven.state.team', return_value={'engine': 'deepseek', 'model': 'shared-fixture'}), \
                 patch('righaven.tools.delegate', return_value=json.dumps({'ok': True, 'handoff': {'checks': []}})) as worker:
                harness_plan.func(runtime=runtime, brief='Proposta iniziale', outcome_json=json.dumps({'result': 'Proposta iniziale', 'format': 'Documento testuale modificabile'}), roles_json=json.dumps([role()]),
                    memory_json=json.dumps({'decisione': 'Prima la proposta'}),
                    steps_json=json.dumps([{'id': 'prepare', 'agent': 'workspace', 'role_id': 'design', 'goal': 'Proposta verificabile'}]))
                harness_delegate.func(agent='workspace', task='Preparare la proposta', step_id='prepare', runtime=runtime)
                args = worker.call_args
                compiled = args.kwargs['role']
                self.assertEqual(compiled['id'], 'design')
                self.assertIn('Confrontare alternative', load_compiled(root, compiled))
                self.assertEqual(read_document(root, args.kwargs['acceptance']['request_documents'][0]), original)
                self.assertEqual(compiled['request_hash'], args.kwargs['acceptance']['hash'])
                self.assertEqual(read_project(root)['steps'][0]['role_title'], compiled['title'])
                # Changing a real requirement compiles a new version, preserving the old file.
                runtime.state['messages'].append(SimpleNamespace(type='human', id='clarification', content='Confronta due alternative'))
                harness_delegate.func(agent='workspace', task='Aggiornare la proposta', step_id='prepare', runtime=runtime)
                updated = worker.call_args.kwargs['role']
                self.assertNotEqual(updated['version'], compiled['version'])
                self.assertIn('Missione', load_compiled(root, compiled))
                self.assertEqual(worker.call_count, 2)
                other = role(); other.update(id='verify', title='Responsabile delle verifiche')
                harness_plan.func(runtime=runtime, roles_json=json.dumps([role(), other]),
                    steps_json=json.dumps([{'id': 'prepare', 'agent': 'workspace', 'role_id': 'verify', 'goal': 'Verificare alternative'}]))
                harness_delegate.func(agent='workspace', task='Controllare la proposta', step_id='prepare', runtime=runtime)
                self.assertEqual(worker.call_args.kwargs['role']['id'], 'verify')
                self.assertEqual(read_project(root)['steps'][0]['role_title'], other['title'])

    def test_briefing_blocks_worker_until_material_choices_are_resolved(self):
        from righaven.projects import read_project
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='initial', content='Crea il progetto')]})
            with patch('righaven.tools.workspace_for', return_value=root), \
                 patch('righaven.state.team', return_value={'engine': 'deepseek', 'model': 'fixture'}), \
                 patch('righaven.tools.delegate', return_value=json.dumps({'ok': True, 'handoff': {'checks': []}})) as worker:
                response = json.loads(harness_delegate.func(agent='wordcraft', task='Avvia tutto', runtime=runtime))
                self.assertTrue(response['needs_briefing'])
                self.assertFalse(worker.called)
                self.assertEqual(read_project(root)['status'], 'clarifying')
                harness_plan.func(runtime=runtime, outcome_json=json.dumps({'result': 'Prodotto richiesto', 'questions': ['Quale forma deve avere la consegna?']}))
                response = json.loads(harness_delegate.func(agent='wordcraft', task='Avvia comunque', runtime=runtime))
                self.assertTrue(response['needs_briefing'])
                self.assertFalse(worker.called)
                with self.assertRaisesRegex(ValueError, 'nuova risposta reale'):
                    harness_plan.func(runtime=runtime, outcome_json=json.dumps({'result': 'Prodotto richiesto', 'format': 'Documento', 'questions': []}))
                runtime.state['messages'].append(SimpleNamespace(type='human', id='answer', content='Documento impaginato e sorgente modificabile'))
                harness_plan.func(runtime=runtime, outcome_json=json.dumps({'result': 'Prodotto richiesto', 'format': 'Documento impaginato con sorgente modificabile', 'questions': []}))
                response = json.loads(harness_delegate.func(agent='wordcraft', task='Prepara la prima versione', runtime=runtime))
                self.assertTrue(response['ok'])
                self.assertEqual(worker.call_count, 1)
                self.assertIn('Documento impaginato con sorgente modificabile', worker.call_args.args[1])
                self.assertFalse(read_project(root)['orientation']['needs_briefing'])

    def test_tool_memory_is_compact_and_delivery_requirements_reach_the_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request-one', content='Crea un robot con musica')]})
            folder = root / 'outputs/filmcraft/fixture'; folder.mkdir(parents=True)
            movie = folder / 'final.mp4'; movie.write_text('fixture media path')
            reply = {'ok': True, 'response': 'private verbose worker context' * 10000,
                'output_dir': '/mnt/user-data/outputs/filmcraft/fixture',
                'product_verified': True, 'verified_products': ['/mnt/user-data/outputs/filmcraft/fixture/final.mp4'],
                'handoff': {'output_files': ['/mnt/user-data/outputs/filmcraft/fixture/final.mp4'], 'source_files': [],
                    'checks': [{'name': 'Media effettivi', 'status': 'passed', 'evidence': 'fixture'}],
                    'warnings': [], 'delivery': {'source_status': 'included', 'files': [
                        {'path': '/mnt/user-data/outputs/filmcraft/fixture/final.mp4', 'role': 'export', 'format': 'MP4',
                         'open_with': 'Player video', 'editability': 'Video esportato'}]}}}
            with patch('righaven.tools.workspace_for', return_value=root), \
                 patch('righaven.state.team', return_value={'engine': 'deepseek', 'model': 'fixture'}), \
                 patch('righaven.tools.delegate', return_value=json.dumps(reply)) as worker:
                harness_plan.func(runtime=runtime, brief='Robot con musica', project_type='animated_video', outcome_json=json.dumps({'result': 'Video con musica', 'format': 'MP4 con progetto modificabile'}))
                compact = harness_delegate.func(agent='filmcraft', task='Integra il risultato completo', runtime=runtime, purpose='delivery')
                self.assertLess(len(compact), 5000)
                self.assertNotIn('private verbose', compact)
                self.assertTrue(json.loads(compact)['ok'])
                self.assertEqual(worker.call_args.kwargs['requirements'], {'video': True, 'audio': True})
                self.assertEqual(worker.call_args.kwargs['purpose'], 'delivery')
                with self.assertRaisesRegex(ValueError, 'sorgenti incompleti'):
                    harness_plan.func(runtime=runtime, status='ready',
                        product_path='/mnt/user-data/outputs/filmcraft/fixture/final.mp4', summary='Video pronto')

    def test_large_handoff_keeps_early_failure_visible_in_actual_tool_wrapper(self):
        from righaven.project_skills import read_document
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request', content='Specific requested product')]})
            checks = [{'name': 'Critical mismatch', 'status': 'failed', 'evidence': 'Actual constraint not met'}] + [
                {'name': 'Passing check ' + str(i), 'status': 'passed', 'evidence': 'Fixture evidence'} for i in range(20)]
            result = {'ok': True, 'handoff': {'checks': checks, 'delivery': {'source_status': 'included', 'files': [
                {'path': '/mnt/user-data/outputs/wordcraft/item-' + str(i) + '.txt', 'role': 'editable_source',
                 'open_with': 'Long native opening instructions ' * 100, 'reopen': {'status': 'passed', 'evidence': 'Evidence ' * 100}}
                for i in range(20)]}}}
            with patch('righaven.tools.workspace_for', return_value=root), patch('righaven.state.team', return_value={'engine': 'codex', 'model': 'shared'}), patch('righaven.tools.delegate', return_value=json.dumps(result)):
                harness_plan.func(runtime=runtime, brief='Requested result', outcome_json=json.dumps({'result': 'Actual product', 'format': 'Editable document'}))
                text = harness_delegate.func(agent='wordcraft', task='Produce', runtime=runtime)
            compact = json.loads(text)
            self.assertLessEqual(len(text), 8000)
            self.assertEqual(compact['decision'], 'needs_revision')
            self.assertEqual(compact['check_counts']['failed'], 1)
            self.assertEqual(compact['check_counts']['passed'], 20)
            self.assertIn('Critical mismatch', text)
            full = json.loads(read_document(root, {'path': compact['details_path'], 'sha256': compact['details_sha256']}))
            self.assertEqual(full['outputs'][0]['reopen']['status'], 'passed')

    def test_one_user_turn_cannot_loop_on_quota_but_an_explicit_continue_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request-one')]})
            with patch('righaven.tools.workspace_for', return_value=Path(directory)), \
                 patch('righaven.state.team', return_value={'engine': 'gemini', 'model': 'fixture'}), \
                 patch('righaven.tools.delegate', return_value=json.dumps({'ok': False, 'error': 'Individual quota reached'})) as worker:
                harness_plan.func(runtime=runtime, brief='Correggi la posa', outcome_json=json.dumps({'result': 'Posa corretta', 'format': 'Progetto modificabile e anteprima'}))
                for _ in range(2):
                    harness_delegate.func(agent='effectcraft', task='Correggi la posa', runtime=runtime, step_id='motion')
                self.assertEqual(worker.call_count, 1)
                runtime.state['messages'].append(SimpleNamespace(type='human', id='explicit-continue'))
                harness_delegate.func(agent='effectcraft', task='Riprendi la posa', runtime=runtime, step_id='motion')
                self.assertEqual(worker.call_count, 2)

    def test_lesson_tool_exposes_proposal_but_no_acceptance_argument(self):
        from righaven.team_routing import shared_run
        from righaven.tools import source_turn
        schema=harness_lessons.tool_call_schema.model_json_schema()
        self.assertIn('lesson_json',schema['properties'])
        self.assertNotIn('accepted',schema['properties'])
        self.assertNotIn('runtime',schema['properties'])
        runtime=SimpleNamespace(config=shared_run({'input':{'messages':[{'role':'user','content':'Risposta'}]}})['config'])
        first=source_turn(runtime)
        self.assertTrue(first)
        self.assertEqual(source_turn(runtime),first)
        runtime.config=shared_run({'input':None})['config']
        self.assertEqual(source_turn(runtime),'')

    def test_lesson_tool_recovers_historical_failed_handoff_without_approval(self):
        from test_production_observations import ProductionObservationsTests
        from righaven.lessons import accepted
        from righaven.tools import experience_root
        fixture = ProductionObservationsTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runtime = SimpleNamespace(config={'configurable': {'thread_id':'historical-thread'}})
        with patch('righaven.tools.workspace_for', return_value=fixture.workspace):
            result = json.loads(harness_lessons.func(runtime=runtime))
            self.assertEqual(len(result['pending_sources']), 1)
            self.assertEqual(result['pending_sources'][0]['status'], 'reported_failure')
            self.assertEqual(accepted(experience_root(runtime)), set())

    def test_large_learning_evidence_stays_addressable_without_overflowing_control_context(self):
        from righaven.tools import lesson_reply
        from righaven.project_skills import read_document
        with tempfile.TemporaryDirectory() as directory:
            workspace=Path(directory)
            result={'pending_sources':[{'id':str(i)*64,'criterion':'Useful operational lesson',
                'evidence':'Long observed evidence '*1000,'producer_method':{'procedure':['Actual step '*1000]}} for i in range(6)]}
            with patch('righaven.tools.workspace_for',return_value=workspace):
                text=lesson_reply(SimpleNamespace(),result)
            self.assertLessEqual(len(text),8000)
            value=json.loads(text)
            self.assertEqual(len(value['pending_sources']),6)
            full=json.loads(read_document(workspace,{'path':value['details_path'],'sha256':value['details_sha256']}))
            self.assertEqual(full,result)

    def test_nullable_reopen_metadata_does_not_turn_saved_delivery_into_tool_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=SimpleNamespace(state={'messages':[SimpleNamespace(type='human',id='request',content='Create a document')]})
            result={'ok':True,'handoff':{'checks':[],'delivery':{'source_status':'included','files':[
                {'path':'/mnt/user-data/outputs/document.docx','role':'editable_source','reopen':None}]}}}
            with patch('righaven.tools.workspace_for',return_value=root),patch('righaven.state.team',return_value={'engine':'codex','model':'shared'}),patch('righaven.tools.delegate',return_value=json.dumps(result)):
                harness_plan.func(runtime=runtime,brief='Document',outcome_json=json.dumps({'result':'Document','format':'Editable document'}))
                reply=json.loads(harness_delegate.func(agent='wordcraft',task='Create',runtime=runtime))
                from righaven.project_skills import read_document
                full=json.loads(read_document(root,{'path':reply['details_path'],'sha256':reply['details_sha256']})) if reply.get('details_path') else reply
            self.assertTrue(reply['ok']);self.assertEqual(full['outputs'][0]['reopen']['status'],'not_run')

    def test_native_end_hook_presents_existing_files_without_another_model_turn_or_approval(self):
        from langchain.agents import create_agent
        from langchain_core.messages import AIMessage,HumanMessage,ToolMessage
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from righaven_core.agents.thread_state import ThreadState
        from righaven.completion_middleware import ProjectCompletionMiddleware
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'outputs/job';out.mkdir(parents=True);file=out/'document.pdf';file.write_bytes(b'existing published fixture')
            virtual='/mnt/user-data/outputs/job/document.pdf'
            project={'id':'fixture','status':'review','product_path':virtual,'results':[{'path':virtual,'role':'export','delivery_id':'job'}]}
            model=FakeMessagesListChatModel(responses=[AIMessage('Document available for review')])
            graph=create_agent(model,tools=[],middleware=[ProjectCompletionMiddleware()],state_schema=ThreadState)
            resolver=SimpleNamespace(resolve_virtual_path=lambda *a,**k:file)
            with patch('righaven.completion_middleware.workspace_for',return_value=root),patch('righaven.completion_middleware.read_project',return_value=project),patch('righaven_core.tools.builtins.present_file_tool.get_paths',return_value=resolver):
                result=graph.invoke({'messages':[HumanMessage('Show the saved result')],'thread_data':{'outputs_path':str(root/'outputs')}},config={'configurable':{'thread_id':'fixture'}},context={'user_id':'owner'})
            self.assertEqual(result['artifacts'],[virtual])
            generated=[m for m in result['messages'] if isinstance(m,AIMessage) and m.additional_kwargs.get('righaven_auto_presentation')]
            self.assertEqual(len(generated),1)
            self.assertEqual(generated[0].tool_calls[0]['name'],'present_files')
            self.assertTrue(any(isinstance(m,ToolMessage) and m.tool_call_id==generated[0].tool_calls[0]['id'] for m in result['messages']))
            self.assertEqual(project['status'],'review')
