"""Use RigHaven's native middleware lifecycle for whole-conversation auditing."""
import asyncio
import json
import uuid
from langchain.agents.middleware import AgentMiddleware
from langgraph.errors import GraphBubbleUp
from .audit_log import append


def runtime_config(runtime):
    config=getattr(runtime,'config',None)
    if not isinstance(config,dict):
        from langgraph.config import get_config
        config=get_config()
    return config


def workspace_for(runtime):
    from righaven_core.config.paths import get_paths
    from righaven_core.runtime.user_context import resolve_runtime_user_id
    thread=runtime_config(runtime).get('configurable',{}).get('thread_id')
    if not thread:raise ValueError('Registro senza conversazione')
    return get_paths().sandbox_user_data_dir(thread,user_id=resolve_runtime_user_id(runtime))


def scope(runtime):
    config=runtime_config(runtime).get('configurable',{})
    root=workspace_for(runtime)
    turn=config.get('righaven_user_turn')
    if turn:
        append(root,'Utente','Messaggio ricevuto','received',identifier='turn:'+turn)
    context=getattr(runtime,'context',None)
    agent=(context.get('agent_name') if isinstance(context,dict) else None) or config.get('righaven_agent_name')
    return root, 'Agente '+agent if agent else 'Coordinatore'


def result_status(result):
    if getattr(result,'status',None)=='error':return 'failed'
    content=getattr(result,'content',None)
    if isinstance(content,str):
        try:
            value=json.loads(content)
            if isinstance(value,dict) and value.get('ok') is False:return 'failed'
        except ValueError:
            if content.startswith('Error:'):return 'failed'
    return 'completed'


class ConversationAuditMiddleware(AgentMiddleware):
    def validate_model_calls(self, request, response):
        """Run before special middleware can consume an invalid clarification call."""
        from langchain_core.utils.function_calling import convert_to_openai_tool
        from .tool_contracts import argument_error
        schemas={}
        for tool in getattr(request,'tools',[]):
            converted=convert_to_openai_tool(tool)
            if 'function' not in converted:continue
            spec=converted['function']
            schemas[spec['name']]=spec.get('parameters', {'type':'object'})
        for i,message in enumerate(getattr(response,'result',[])):
            errors={}
            for call in getattr(message,'tool_calls',[]):
                if call['name'] not in schemas:
                    errors[call['id']]={'ok':False,'changed':False,'code':'unknown_tool','allowed_tools':sorted(schemas)}
                else:
                    error=argument_error(call.get('args',{}),schemas[call['name']])
                    if error:errors[call['id']]=error
            if len(message.tool_calls)>1:
                for call in message.tool_calls:
                    if call['name']=='harness_method' and call.get('args',{}).get('objective'):
                        errors[call['id']]={'ok':False,'changed':False,'code':'objective_transition_must_be_separate',
                            'instruction':'Start the new objective alone. Then read its authoritative state before planning or delegating. No call in this batch ran.'}
            if errors:
                response.result[i]=message.model_copy(update={'additional_kwargs':{
                    **message.additional_kwargs,'righaven_invalid_calls':errors}})
        return response

    def failure(self, request, payload):
        from langchain_core.messages import ToolMessage
        from .tool_contracts import signature
        call = request.tool_call
        return ToolMessage(content=json.dumps(payload, ensure_ascii=False), tool_call_id=call['id'],
                           name=call['name'], status='error', additional_kwargs={'righaven_failed_call': signature(call)})

    def intercept(self, request):
        """All providers use the same executable contract and published-file namespace."""
        from .tool_contracts import argument_error, repeated_failures
        call = request.tool_call
        schema = getattr(getattr(request, 'tool', None), 'tool_call_schema', None)
        if schema is not None:
            schema = schema if isinstance(schema, dict) else schema.model_json_schema()
            problem = argument_error(call.get('args', {}), schema)
            if problem:
                return self.failure(request, problem)
        if repeated_failures(request.state.get('messages', []), call) >= 2:
            return self.failure(request, {'ok': False, 'changed': False, 'retry_blocked': True,
                'code': 'repeated_control_error', 'instruction': 'Do not repeat this operation. Read the current phase next_action and correct the failed precondition. Existing files and other activities remain available.'})
        if call['name'] in ('read_file', 'ls', 'glob'):
            from .published_files import reference, read, inventory
            args = call.get('args', {})
            path = reference(args.get('path', ''), request.state)
            if str(path) == '/mnt/user-data/outputs' or str(path).startswith('/mnt/user-data/outputs/'):
                from langchain_core.messages import ToolMessage
                root = workspace_for(request.runtime)
                result = read(root, path, start_line=args.get('start_line'), end_line=args.get('end_line')) if call['name']=='read_file' else inventory(root, path, args.get('pattern', '*'))
                return ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call['id'], name=call['name'])
        if call['name'] == 'ask_clarification':
            from .journeys import compact, view
            journey = view(workspace_for(request.runtime))
            if journey and journey['awaiting_owner']:
                return self.failure(request, {'ok': False, 'changed': False, 'code': 'owner_decision_pending',
                    'journey': compact(journey), 'instruction': 'A reviewed result already awaits the owner in the task card. Present the result and end the turn. Do not ask for the same approval in chat.'})
        return None

    def annotate_failure(self, request, result):
        from .tool_contracts import signature
        if result_status(result)=='failed' and hasattr(result, 'model_copy'):
            return result.model_copy(update={'additional_kwargs': {**getattr(result,'additional_kwargs',{}),
                'righaven_failed_call': signature(request.tool_call)}})
        if request.tool_call['name'] in ('harness_delegate','harness_package_check','harness_method') and hasattr(result,'model_copy'):
            try:
                value=json.loads(result.content)
                progress=value.get('ok') is True and not value.get('duplicate') or value.get('changed') is True
                if progress:
                    return result.model_copy(update={'additional_kwargs':{**getattr(result,'additional_kwargs',{}),'righaven_control_progress':True}})
            except (ValueError,TypeError,AttributeError):pass
        return result

    def before_agent(self,state,runtime):
        try:
            root,actor=scope(runtime)
            turn=runtime_config(runtime).get('configurable',{}).get('righaven_user_turn')
            append(root,actor,'Preparazione del turno','started',identifier='begin:'+str(turn)+':'+actor if turn else None)
        except (AttributeError,ValueError,OSError):pass

    async def abefore_agent(self,state,runtime):
        return self.before_agent(state,runtime)

    def begin(self,request,kind):
        try:
            root,actor=scope(request.runtime)
            call=getattr(request,'tool_call',{}) or {}
            operation='Strumento: '+str(call.get('name','')) if kind=='tool' else 'Richiesta al modello'
            correlation=call.get('id') or uuid.uuid4().hex
            append(root,actor,operation,'started',correlation=correlation)
            return root,actor,operation,correlation
        except (AttributeError,ValueError,OSError):return None

    def end(self,event,status,error=None):
        if event:
            root,actor,operation,correlation=event
            # Error contents may contain provider payloads. Record the class;
            # tool-specific public diagnostics remain in the project/job log.
            append(root,actor,operation,status,detail=type(error).__name__ if error else '',correlation=correlation)

    def after_agent(self,state,runtime):
        try:
            root,actor=scope(runtime)
            turn=runtime_config(runtime).get('configurable',{}).get('righaven_user_turn')
            append(root,actor,'Turno concluso','completed',identifier='end:'+str(turn)+':'+actor if turn else None)
        except (AttributeError,ValueError,OSError):pass

    async def aafter_agent(self,state,runtime):
        return self.after_agent(state,runtime)

    def wrap_model_call(self,request,handler):
        event=self.begin(request,'model')
        try:result=handler(request)
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,'completed');return self.validate_model_calls(request,result)

    async def awrap_model_call(self,request,handler):
        event=self.begin(request,'model')
        try:result=await handler(request)
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,'completed');return self.validate_model_calls(request,result)

    def wrap_tool_call(self,request,handler):
        event=self.begin(request,'tool')
        try:
            result=self.intercept(request)
            if result is None:result=handler(request)
        except (ValueError,TypeError) as error:
            result=self.failure(request,{'ok':False,'changed':None,'code':'operation_rejected','error':str(error)[:1500],
                'instruction':'Read harness_journey or harness_plan for the current next_action. Correct this precondition before retrying; do not claim a state change.'})
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,result_status(result));return self.annotate_failure(request,result)

    async def awrap_tool_call(self,request,handler):
        event=self.begin(request,'tool')
        try:
            result=await asyncio.to_thread(self.intercept,request)
            if result is None:result=await handler(request)
        except (ValueError,TypeError) as error:
            result=self.failure(request,{'ok':False,'changed':None,'code':'operation_rejected','error':str(error)[:1500],
                'instruction':'Read harness_journey or harness_plan for the current next_action. Correct this precondition before retrying; do not claim a state change.'})
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,result_status(result));return self.annotate_failure(request,result)
