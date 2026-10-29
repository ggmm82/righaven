"""Bounded completion feedback through RigHaven's native agent middleware."""
from typing import NotRequired
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, SystemMessage
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

    @hook_config(can_jump_to=['model'])
    def after_model(self, state, runtime):
        last = next((m for m in reversed(state.get('messages', [])) if isinstance(m, AIMessage)), None)
        if not last:
            return None
        update = {'harness_completion_reminder': ''}
        if isinstance(getattr(runtime, 'context', None), dict) and runtime.context.get('stop_reason'):
            return update  # Native loop/token/time budgets retain authority.
        if last.tool_calls:
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
            # One bounded learning pass at a genuine stopping point, never a
            # render loop or mandatory approval of every observation.
            if (project and (not continuing or count >= self.MAX_NUDGES or unchanged)
                    and not state.get('harness_learning_nudged')
                    and project.get('status') != 'clarifying'
                    and not any((project.get('user_control') or {}).get(k) for k in ('paused','deliver_now'))
                    and (project.get('attention') or {}).get('code') not in ('provider_auth','provider_quota','resource_memory','work_cancelled')):
                sources = learning_sources(runtime)
                if sources:
                    append(root, 'Memoria', 'Valutazione delle lezioni richiesta', 'progress',
                           detail='Una sola valutazione di massimo tre fonti della conversazione; nessuna approvazione automatica di metodi.')
                    return {**update, 'jump_to':'model', 'harness_learning_nudged':True,
                        'harness_completion_reminder':'Prima di chiudere valuta brevemente le osservazioni già conservate con '
                        'harness_lessons(current_project_only=true). Seleziona al massimo tre fonti significative: '
                        + ', '.join(s['id'] for s in sources) + '. Leggi prove e limiti, generalizza solo singole lezioni utili '
                        'o motiva perché non sono trasferibili. Le note tecniche richiedono il test verificabile per attivarsi; '
                        'i metodi di realizzazione richiedono accettazione dell’utente. Non approvare metodi, non inventare prove, '
                        'non rigenerare prodotti né bloccare la consegna per esaurire il backlog. Poi presenta risultato, limiti e prossimo passo reale.'}
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

    @hook_config(can_jump_to=['model'])
    async def aafter_model(self, state, runtime):
        return self.after_model(state, runtime)

    def augmented(self, request):
        try:
            project=read_project(workspace_for(request.runtime))
            if (project or {}).get('user_control',{}).get('deliver_now'):
                return request.override(messages=[*request.messages,SystemMessage(content=
                    'L’utente ha premuto Consegna ora. Non avviare altre attività, revisioni o raccolte di lezioni. '
                    'Presenta adesso i risultati già disponibili, i link ai file e i limiti delle verifiche; poi fermati.')])
        except (AttributeError,ValueError,OSError):pass
        reminder = request.state.get('harness_completion_reminder')
        # Control feedback is request-only: never persist a synthetic user turn
        # or change the immutable user acceptance contract.
        return request.override(messages=[*request.messages, SystemMessage(content=reminder)]) if reminder else request

    def wrap_model_call(self, request, handler):
        return handler(self.augmented(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self.augmented(request))
