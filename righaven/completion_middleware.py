"""Bounded completion feedback through RigHaven's native agent middleware."""
from typing import NotRequired
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from .audit_middleware import workspace_for,runtime_config
from .audit_log import append
from .completion_policy import needs_continuation,production_call
from .projects import read_project, mark_incomplete_turn


def learning_sources(runtime):
    from .tools import experience_root
    from .lessons import pending
    thread = (getattr(runtime, 'config', None) or {}).get('configurable', {}).get('thread_id')
    return pending(experience_root(runtime), limit=3, source_thread=thread, meaningful_only=True) if thread else []


class CompletionState(AgentState):
    harness_production_started: NotRequired[bool]
    harness_completion_nudges: NotRequired[int]
    harness_completion_reminder: NotRequired[str]
    harness_work_generation: NotRequired[int]
    harness_reminded_generation: NotRequired[int]
    harness_learning_nudged: NotRequired[bool]
    harness_presentation_signature: NotRequired[str]


class ProjectCompletionMiddleware(AgentMiddleware):
    state_schema = CompletionState
    MAX_NUDGES = 2

    def before_agent(self, state, runtime):
        # Repair historical contracts that captured the UI's resume button as
        # a new product requirement, even when the model only summarizes next.
        context=getattr(runtime,'context',None)
        if not (isinstance(context,dict) and context.get('is_subagent')):
            from .project_controls import operational_resume
            for message in reversed(state.get('messages',[])):
                kind=message.get('type',message.get('role')) if isinstance(message,dict) else getattr(message,'type','')
                if kind not in ('human','user'):continue
                text=message.get('content','') if isinstance(message,dict) else getattr(message,'content','')
                if isinstance(text,list):text='\n'.join(b.get('text','') for b in text if isinstance(b,dict) and b.get('type')=='text')
                if operational_resume(text):
                    try:
                        from .projects import sync_acceptance
                        sync_acceptance(workspace_for(runtime),[text])
                    except (AttributeError,ValueError,OSError,RuntimeError):pass
                break
        return {'harness_production_started': False, 'harness_completion_nudges': 0, 'harness_completion_reminder': '',
                'harness_work_generation':0, 'harness_reminded_generation':-1, 'harness_learning_nudged':False}

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    def after_agent(self,state,runtime):
        """Publish existing files even if the model omitted the native tool call.

        This runs after the graph ends: no additional model turn, production or
        approval. The actual native tool validates owner/thread output paths.
        """
        try:
            context=getattr(runtime,'context',None)
            if isinstance(context,dict) and context.get('is_subagent'):return None
            from .presentation import presentation
            root=workspace_for(runtime)
            plan=presentation(root,read_project(root),state)
            if not plan:return None
            update={'harness_presentation_signature':plan['signature']}
            if not plan['paths']:return update
            from types import SimpleNamespace
            from uuid import uuid4
            from righaven_core.tools.builtins.present_file_tool import present_file_tool
            call_id='rh-present-'+uuid4().hex
            tool_runtime=SimpleNamespace(state=state,context=context,config=runtime_config(runtime))
            result=present_file_tool.func(runtime=tool_runtime,filepaths=plan['paths'],tool_call_id=call_id)
            if not result.update.get('artifacts'):
                append(root,'Consegna','File non presentati','failed',detail='Il controllo nativo dei percorsi non è riuscito.')
                return None
            message=AIMessage(content=plan['note'],tool_calls=[{'name':'present_files','id':call_id,'args':{'filepaths':plan['paths']}}],
                              additional_kwargs={'righaven_auto_presentation':True})
            append(root,'Consegna','File presentati','completed',detail='Risultato e sorgenti pubblicati senza modificare il giudizio di qualità.')
            return {**update,**result.update,'messages':[message,*result.update['messages']]}
        except (AttributeError,ValueError,OSError,RuntimeError):
            return None

    async def aafter_agent(self,state,runtime):
        return self.after_agent(state,runtime)

    @hook_config(can_jump_to=['model', 'end'])
    def after_model(self, state, runtime):
        last = next((m for m in reversed(state.get('messages', [])) if isinstance(m, AIMessage)), None)
        if not last:
            return None
        update = {'harness_completion_reminder': ''}
        if isinstance(getattr(runtime, 'context', None), dict) and runtime.context.get('stop_reason'):
            return update  # Native loop/token/time budgets retain authority.
        if last.tool_calls:
            from .tool_contracts import repeated_failures
            if all(repeated_failures(state.get('messages', []), call) >= 2 for call in last.tool_calls):
                try:
                    root=workspace_for(runtime)
                    mark_incomplete_turn(root)
                    append(root,'Coordinatore','Ciclo di controllo interrotto','failed',detail='Operazioni identiche respinte due volte; nessuna nuova esecuzione.')
                except (AttributeError,ValueError,OSError):
                    pass
                stopped=last.model_copy(update={'tool_calls':[], 'content':
                    'Ho fermato un ciclo di operazioni respinte che non faceva avanzare il lavoro. '
                    'Il risultato non è completo; i file già prodotti sono conservati. '
                    'Lo stato del progetto resta quello mostrato nella scheda: le approvazioni non sono state modificate.'})
                return {**update,'messages':[stopped],'jump_to':'end'}
            invalid=last.additional_kwargs.get('righaven_invalid_calls',{})
            if invalid:
                import json
                from .tool_contracts import signature
                try:
                    for call in last.tool_calls:
                        if call['id'] in invalid:
                            append(workspace_for(runtime),'Coordinatore','Convalida: '+call['name'],'failed',
                                   detail='Parametri non validi; operazione non eseguita.',correlation=call['id'])
                except (AttributeError,ValueError,OSError):pass
                # Atomic rejection: a malformed control batch cannot partly advance
                # the plan, run a worker or interrupt the owner with a wrong form.
                feedback=[ToolMessage(tool_call_id=call['id'],name=call['name'],status='error',
                    content=json.dumps(invalid.get(call['id'],{'ok':False,'changed':False,'code':'batch_deferred',
                        'instruction':'Correct the invalid sibling call before retrying this batch.'})),
                    additional_kwargs={'righaven_failed_call':signature(call)} if call['id'] in invalid else {}) for call in last.tool_calls]
                return {**update,'messages':feedback,'jump_to':'model'}
            if any(c['name']=='ask_clarification' for c in last.tool_calls):
                try:
                    from .journeys import view
                    journey=view(workspace_for(runtime))
                    if journey and journey['awaiting_owner']:
                        stopped=last.model_copy(update={'tool_calls':[],'content':
                            'Il risultato verificato è pronto nella scheda del progetto. Usa «Approva fase» o «Chiedi correzioni»: la decisione viene salvata e la squadra prosegue.'})
                        return {**update,'messages':[stopped],'jump_to':'end'}
                except (AttributeError,ValueError,OSError):pass
            if any(c['name'] == 'harness_lessons' and (c.get('args',{}).get('lesson_json') or c.get('args',{}).get('dismiss_reason')) for c in last.tool_calls):
                update['harness_learning_nudged'] = True
            if any(production_call(c) for c in last.tool_calls):
                update['harness_production_started'] = True
                update['harness_work_generation'] = state.get('harness_work_generation',0) + 1
            return update
        # Respect native provider/safety/loop terminalization and parsing errors.
        if last.invalid_tool_calls or any(k in last.additional_kwargs for k in
                ('righaven_error_fallback', 'model_length_termination', 'safety_termination', 'loop_detection')):
            return update
        if not state.get('harness_production_started'):
            return update  # An explanation or a review-only turn is not new production.
        try:
            root = workspace_for(runtime)
            project = read_project(root)
            continuing = needs_continuation(project)
            count = state.get('harness_completion_nudges', 0)
            unchanged = count > 0 and state.get('harness_work_generation',0) == state.get('harness_reminded_generation',-1)
            # Learning is preserved during delegation; it must never add a
            # mandatory model turn before delivery or an owner decision.
            if not continuing:
                return update
            if count >= self.MAX_NUDGES or unchanged:
                mark_incomplete_turn(root)
                append(root, 'Coordinatore', 'Obiettivo non completato', 'failed',
                       detail='Nessuna nuova lavorazione dopo il richiamo; evitate risposte ripetute.' if unchanged else 'Terminati due richiami di completamento; file conservati, nessuna approvazione.')
                return update
            reminder = ('Il turno di produzione sta terminando ma il progetto non è completo. '
                'Prossimo obiettivo registrato: ' + str(project.get('next_action', ''))[:500] + '. '
                'Procedi con la correzione mirata o il completamento già autorizzati, riusando i sorgenti. '
                'Non ripetere campioni equivalenti né rigenerare per un controllo sensoriale indisponibile. '
                'Se serve davvero una decisione/input/budget dell’utente, registra strategy state=needs_user, '
                'stop_reason e user_action concreti e poni la domanda necessaria. Non dichiarare finito il prodotto incompleto.')
            append(root, 'Coordinatore', 'Ripresa del lavoro incompleto', 'progress',
                   detail='Richiamo di completamento ' + str(count + 1) + '/2')
            return {**update, 'jump_to': 'model', 'harness_completion_nudges': count + 1,
                    'harness_reminded_generation':state.get('harness_work_generation',0),
                    'harness_completion_reminder': reminder}
        except (AttributeError, ValueError, OSError):
            return update

    @hook_config(can_jump_to=['model', 'end'])
    async def aafter_model(self, state, runtime):
        return self.after_model(state, runtime)

    def augmented(self, request):
        control = None
        shared = ''
        try:
            project=read_project(workspace_for(request.runtime))
            context=getattr(request.runtime,'context',None)
            if not (isinstance(context,dict) and context.get('is_subagent')):
                import json
                from .collaboration import GUIDANCE
                from .connections import assigned
                shared = GUIDANCE + '\nAuthorized task connections (metadata only): ' + json.dumps(assigned(workspace_for(request.runtime)),ensure_ascii=False)
                from .source_edits import edits
                edited=edits(workspace_for(request.runtime)/'.righaven-project')
                if edited:
                    shared += '\nOwner source copies (originals and exports unchanged): ' + json.dumps(edited[-5:],ensure_ascii=False) + '\nUse these copies when the user asks to incorporate their edits. Saving a copy does not approve or regenerate a final delivery.'
                if (project or {}).get('scope'):
                    scope=project['scope']
                    shared += '\nCurrent objective and retained base (old recipe is reference only): '+json.dumps({k:scope.get(k) for k in ('goal','parent','reference_recipe')},ensure_ascii=False)+'\nWork toward this objective. Reuse relevant prior files, but do not carry old approvals, recipe gates or claims of validation into new work. Explain what will stay and what changes; ask only decisive unknowns.'
                if (project or {}).get('method_decision'):
                    shared += '\nLatest owner method decision: ' + json.dumps(project['method_decision'],ensure_ascii=False)
            from .journeys import view, compact
            journey=(project or {}).get('journey') or view(workspace_for(request.runtime))
            if journey:
                import json
                value=compact(journey)
                control=SystemMessage(content='Live task state (authoritative; do not rewrite it): '+json.dumps(
                    {k:value[k] for k in ('mode','revision','current','awaiting_owner','next_action','connections')},ensure_ascii=False)+
                    '\nUse published read_file artifacts, not a second sandbox. Read only context needed for the next result. '
                    'Lessons are preserved and evaluated after delivery. A chat reply never silently approves a phase.')
            if (project or {}).get('user_control',{}).get('deliver_now'):
                return request.override(messages=[*request.messages,SystemMessage(content=
                    'L’utente ha premuto Consegna ora. Non avviare altre attività, revisioni o raccolte di lezioni. '
                    'Presenta adesso i risultati già disponibili, i link ai file e i limiti delle verifiche; poi fermati.')])
        except (AttributeError,ValueError,OSError):pass
        reminder = request.state.get('harness_completion_reminder')
        # Control feedback is request-only: never persist a synthetic user turn
        # or change the immutable user acceptance contract.
        content = '\n'.join(s for s in (shared, control.content if control else '', reminder) if s)
        additions=[SystemMessage(content=content)] if content else []
        return request.override(messages=[*request.messages,*additions]) if additions else request

    def wrap_model_call(self, request, handler):
        return handler(self.augmented(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self.augmented(request))
