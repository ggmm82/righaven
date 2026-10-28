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
        self.end(event,'completed');return result

    async def awrap_model_call(self,request,handler):
        event=self.begin(request,'model')
        try:result=await handler(request)
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,'completed');return result

    def wrap_tool_call(self,request,handler):
        event=self.begin(request,'tool')
        try:result=handler(request)
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,result_status(result));return result

    async def awrap_tool_call(self,request,handler):
        event=self.begin(request,'tool')
        try:result=await handler(request)
        except BaseException as error:
            self.end(event,'interrupted' if isinstance(error,(asyncio.CancelledError,GraphBubbleUp)) else 'failed',error);raise
        self.end(event,result_status(result));return result
