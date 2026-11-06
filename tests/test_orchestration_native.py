"""Real LangChain graph replay of malformed calls and inaccessible published artifacts."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from langchain.agents import create_agent
    from langchain_core.tools import tool
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from righaven.audit_middleware import ConversationAuditMiddleware
    from righaven.completion_middleware import ProjectCompletionMiddleware
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    create_agent=None


@unittest.skipIf(create_agent is None,'Requires the native agent SDK')
class NativeOrchestrationTests(unittest.TestCase):
    def test_owner_card_decision_cannot_be_replaced_by_native_chat_clarification(self):
        try:
            from righaven_core.agents.middlewares.clarification_middleware import ClarificationMiddleware
        except ImportError:
            import os
            if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
            self.skipTest('Requires the native core clarification middleware')
        from righaven import journeys
        @tool
        def ask_clarification(question:str)->str:
            """Ask a missing business question."""
            raise AssertionError('duplicate approval must not execute')
        class AskingCoordinator(BaseChatModel):
            @property
            def _llm_type(self):return 'regression-fixture'
            def bind_tools(self,tools,**kwargs):return self
            def _generate(self,messages,stop=None,run_manager=None,**kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='',tool_calls=[
                    {'name':'ask_clarification','id':'approval','args':{'question':'Approvi ancora il catalogo?'}}]))])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);waiting=journeys.start(root,'data-pipeline',{'goal':'A small dashboard'},mode='first_result')
            waiting['awaiting_owner']=['preview'];waiting['stages'][0]['status']='review'
            with patch('righaven.audit_middleware.scope',return_value=(root,'Coordinator')), \
                 patch('righaven.audit_middleware.workspace_for',return_value=root), \
                 patch('righaven.completion_middleware.workspace_for',return_value=root), \
                 patch('righaven.completion_middleware.read_project',return_value=None),patch('righaven.journeys.view',return_value=waiting):
                graph=create_agent(AskingCoordinator(),tools=[ask_clarification],middleware=[
                    ClarificationMiddleware(),ConversationAuditMiddleware(),ProjectCompletionMiddleware()])
                result=graph.invoke({'messages':[HumanMessage('Continue')]})
            self.assertIn('scheda del progetto',result['messages'][-1].content)
            self.assertFalse(result['messages'][-1].tool_calls)

    def test_bad_writes_cannot_degrade_to_reads_and_identical_loop_stops(self):
        executed=[]
        @tool
        def harness_journey(stage_id:str='')->str:
            """Read or change a phase by its actual identifier."""
            executed.append(stage_id)
            return 'should not execute invalid arguments'
        class BrokenCoordinator(BaseChatModel):
            calls:int=0
            @property
            def _llm_type(self):return 'regression-fixture'
            def bind_tools(self,tools,**kwargs):return self
            def _generate(self,messages,stop=None,run_manager=None,**kwargs):
                self.calls+=1
                message=AIMessage(content='I will advance the phases',tool_calls=[{'name':'harness_journey','id':str(self.calls),
                    'args':{'current':'data','stages_json':'[{"id":"understand","status":"completed"}]'}}])
                return ChatResult(generations=[ChatGeneration(message=message)])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);model=BrokenCoordinator()
            with patch('righaven.audit_middleware.scope',return_value=(root,'Coordinator')), \
                 patch('righaven.audit_middleware.workspace_for',return_value=root), \
                 patch('righaven.completion_middleware.workspace_for',return_value=root), \
                 patch('righaven.completion_middleware.read_project',return_value=None):
                agent=create_agent(model,tools=[harness_journey],middleware=[ConversationAuditMiddleware(),ProjectCompletionMiddleware()])
                result=agent.invoke({'messages':[HumanMessage('Create the requested result')]})
            self.assertEqual(executed,[])
            self.assertEqual(model.calls,3,'two recoverable errors, then deterministic termination')
            failures=[m for m in result['messages'] if getattr(m,'type','')=='tool']
            self.assertTrue(all(json.loads(m.content)['changed'] is False for m in failures))
            self.assertIn('non è completo',result['messages'][-1].content)
            self.assertFalse(result['messages'][-1].tool_calls)

    def test_native_file_tool_reads_published_owner_file_without_second_sandbox(self):
        @tool
        def read_file(path:str)->str:
            """Read a file."""
            raise AssertionError('must not acquire the generic coordinator sandbox')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'outputs/job').mkdir(parents=True)
            (root/'outputs/job/report.md').write_text('Actual worker output')
            request=SimpleNamespace(tool=read_file,tool_call={'id':'read','name':'read_file','args':{'path':'art_12345678'}},
                runtime=SimpleNamespace(),state={'messages':[],'tool_artifacts':[{'handle':'art_12345678','real_ref':'/mnt/user-data/outputs/job/report.md'}]})
            with patch('righaven.audit_middleware.scope',return_value=(root,'Coordinator')),patch('righaven.audit_middleware.workspace_for',return_value=root):
                result=ConversationAuditMiddleware().wrap_tool_call(request,lambda _:self.fail('sandbox invoked'))
            self.assertEqual(json.loads(result.content)['content'],'Actual worker output')

    def test_real_async_graph_forwards_guided_phase_to_delegate(self):
        import asyncio
        from righaven.tools import harness_delegate
        class Coordinator(BaseChatModel):
            @property
            def _llm_type(self):return 'async-regression-fixture'
            def bind_tools(self,tools,**kwargs):return self
            def _generate(self,messages,stop=None,run_manager=None,**kwargs):
                if any(getattr(m,'type','')=='tool' for m in messages):message=AIMessage(content='Delegated')
                else:message=AIMessage(content='',tool_calls=[{'name':'harness_delegate','id':'work','args':{
                    'agent':'workspace','task':'Build the selected result','step_id':'build','role_id':'author','purpose':'delivery','phase_id':'delivery'}}])
                return ChatResult(generations=[ChatGeneration(message=message)])
        def run(agent,task,runtime,**kwargs):
            self.assertEqual(kwargs['phase_id'],'delivery')
            self.assertEqual(kwargs['step_id'],'build')
            return json.dumps({'ok':True})
        graph=create_agent(Coordinator(),tools=[harness_delegate])
        with patch('righaven.tools.delegate_step',side_effect=run) as delegated:
            result=asyncio.run(graph.ainvoke({'messages':[HumanMessage('Finish the selected delivery')]}))
            self.assertEqual(delegated.call_count,1)
            self.assertEqual(result['messages'][-1].content,'Delegated')

    def test_real_progress_allows_a_previously_failed_validation_to_recover(self):
        from langchain_core.messages import ToolMessage
        from righaven.tool_contracts import repeated_failures,signature
        call={'id':'validate','name':'harness_validate','args':{}}
        failures=[ToolMessage(content='failed',tool_call_id=str(i),status='error',additional_kwargs={'righaven_failed_call':signature(call)}) for i in range(2)]
        self.assertEqual(repeated_failures(failures,call),2)
        request=SimpleNamespace(tool_call={'id':'work','name':'harness_delegate','args':{}})
        progress=ConversationAuditMiddleware().annotate_failure(request,ToolMessage(content='{"ok":true}',tool_call_id='work'))
        self.assertEqual(repeated_failures([*failures,progress],call),0)
        read=ToolMessage(content='{"project":{}}',tool_call_id='read',name='harness_plan')
        self.assertEqual(repeated_failures([*failures,read],call),2,'Reading a plan is not production progress')

    def test_new_objective_requires_latest_user_input_and_is_separate_from_work(self):
        from righaven.tools import harness_method,harness_plan
        from righaven import projects
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);projects.create_plan(root,'Prior result',[])
            runtime=SimpleNamespace(config={'configurable':{'thread_id':'thread','righaven_user_turn':'new-turn'}},
                state={'messages':[HumanMessage(content='Turn the result into a customer portal',id='new-request')]},context={})
            with patch('righaven.tools.workspace_for',return_value=root):
                with self.assertRaisesRegex(ValueError,'latest user request'):
                    harness_method.func(runtime=runtime,objective='A different goal invented by the coordinator')
                result=json.loads(harness_method.func(runtime=runtime,objective='Turn the result into a customer portal'))
                self.assertTrue(result['changed'])
                self.assertEqual(projects.read_project(root)['scope']['goal'],'Turn the result into a customer portal')
            calls=[{'name':'harness_method','id':'scope','args':{'objective':'Turn the result into a customer portal'}},
                   {'name':'harness_plan','id':'plan','args':{}}]
            request=SimpleNamespace(tools=[harness_method,harness_plan])
            response=SimpleNamespace(result=[AIMessage(content='',tool_calls=calls)])
            invalid=ConversationAuditMiddleware().validate_model_calls(request,response).result[0]
            self.assertEqual(invalid.additional_kwargs['righaven_invalid_calls']['scope']['code'],'objective_transition_must_be_separate')


if __name__=="__main__":unittest.main()
