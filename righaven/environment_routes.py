"""User-owned native Agent environments; deployment preferences never copy skills."""
import asyncio
import json
import logging
import subprocess
import threading
from fastapi import APIRouter, Request, Response, HTTPException, Query
from pydantic import BaseModel, Field
from app.gateway.authz import require_permission
from righaven_core.runtime.user_context import get_effective_user_id
from starlette.concurrency import run_in_threadpool
from .router import same_origin, RuntimeConfig
from . import environments as profiles
from . import environment_runtime as runtimes
from . import environment_preparation as preparation

router=APIRouter(prefix='/api/harness/environments',tags=['Ambienti'])


class Definition(BaseModel):
    name:str=Field(pattern='^[a-z0-9][a-z0-9-]{0,63}$')
    display_name:str=Field(min_length=1,max_length=64)
    purpose:str=Field(min_length=1,max_length=4000)
    instructions:str=Field(default='',max_length=20000)
    skills:list[str]=Field(max_length=200)
    mode:str=Field(default='on_demand',pattern='^(on_demand|preload)$')
    ephemeral:bool=False
    tool_versions:dict[str,str]=Field(default_factory=dict,max_length=128)
    preload_tools:list[str]|None=Field(default=None,max_length=64)


async def native_agents(request):
    from app.gateway.routers.agents import list_agents
    return (await list_agents(request)).agents


async def native_agent(request,name):
    from app.gateway.routers.agents import get_agent
    return await get_agent(name,request)


def summary(user,agent,identity=None,cache=None):
    from .software_identity import compatible
    value=profiles.profile(user,agent)
    if runtimes.enabled():
        target=profiles.preloaded_tools(value['deployment'],value['tools']) if value['deployment']['mode']=='preload' else value['tools']
        from .tool_versions import software_selections,resolved
        chosen=software_selections(user,agent.name,target)
        try:
            # Reading the page or starting a chat must never advance a global
            # Latest pointer. Only an explicit preparation/version action does.
            pins=resolved(chosen,refresh=False)
            value['runtime']=runtimes.available(target,identity,cache,versions=pins)
        except ValueError as error:
            value['runtime']={'status':'version_pending','error':str(error),'tools':target}
        value['selected_versions']=chosen
        value['preloaded_tools']=target if value['deployment']['mode']=='preload' else []
    else:value['runtime']={'status':'legacy','tools':value['tools']}
    active=(user,agent.name) in runtimes.PREPARING
    stored=preparation.read(user,agent.name)
    # A newly verified global Latest must not erase an existing prepared profile.
    # Keep it usable and show the update separately until preparation is explicit.
    retained=stored.get('ready_id')
    if retained and value['runtime']['status']=='on_demand' and {k:v for k,v in stored.get('selection',{}).items() if not k.startswith('provider-')}==value.get('selected_versions',{}):
        previous=runtimes.read(retained)
        if previous and set(target).issubset(previous.get('tools',[])) and runtimes.image_exists(previous,cache) and (not value['runtime'].get('core') or compatible(previous,value['runtime'],runtimes.docker)):
            value['runtime']={**previous,'update_available':True,'requested_id':value['runtime']['id']}
    current=not stored or {k:v for k,v in stored.get('selection',{}).items() if not k.startswith('provider-')}==value.get('selected_versions',{})
    status=preparation.snapshot(user,agent.name,value['runtime'],active)
    if status:status['pending_changes']=not current
    if stored and not current:
        old=stored.get('selection',{});new=value.get('selected_versions',{})
        providers={'provider-agy':'Antigravity','provider-codex':'Codex','provider-claude':'Claude Code'}
        before=[providers[k] for k in providers if k in old]
        after=[providers[k] for k in providers if k in new]
        provider_changed=before!=after
        previous=runtimes.read(retained) if retained else None
        preserved=bool(previous and runtimes.image_exists(previous,cache))
        message=('Il motore della squadra è cambiato: '+(', '.join(before) or 'CLI inclusa')+' → '+(', '.join(after) or 'CLI inclusa')+'.' if provider_changed else 'Le versioni selezionate per questo ambiente sono cambiate.')
        message+=(' La variante precedente è ancora conservata.' if preserved else 'Il registro precedente è conservato; la sua immagine non risulta disponibile.')
        value['configuration_change']={'code':'provider_changed' if provider_changed else 'selection_changed','message':message,'previous_available':preserved,'previous_providers':before,'requested_providers':after}
        if previous and preserved:value['previous_runtime']={k:previous[k] for k in ('id','tools','version_names','installed_versions') if k in previous}
        if status and not active:
            status.update(phase='configuration_changed',label='Configurazione da aggiornare',active=False,historical=True)
        if value['runtime']['status']!='ready' and not active:value['runtime']['preparation_reason']=value['configuration_change']
    if status:
        # During release verification there is no final image ID yet. Never hide
        # this work behind a generic "version pending" state.
        if active and status['phase'] in preparation.ACTIVE and value['runtime']['status'] not in ('installing','adapters','checking','publishing'):
            value['runtime']={**value['runtime'],'status':status['phase'],'error':''}
        elif not active and status['phase'] in ('failed','cancelled','interrupted') and value['runtime']['status']!='ready':
            value['runtime']={**value['runtime'],'status':status['phase'],'error':status.get('error','')}
        value['preparation']=status
    if value['runtime']['status']=='failed':
        failure=value['runtime'].get('failure') or (stored.get('failure') if current else None)
        # Older releases blamed the last installed tool even after a successful
        # native run. Correct that display without rewriting historical records.
        key=value['runtime'].get('id')
        if failure and failure.get('kind')=='verification' and not failure.get('failed_tools') and key:
            text=runtimes.preparation_text(key,since=value['runtime'].get('attempt_started_at'))
            events=[]
            for line in text.splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                if isinstance(event,dict) and event.get('phase'):events.append(event['phase'])
            if events and events[-1]=='verified':
                failure=preparation.diagnosis(text,'Il dettaglio tecnico originale non è stato conservato dalla versione precedente.',phase='publishing')
        if not failure:
            failure=preparation.diagnosis(runtimes.preparation_text(key) if key else '',value['runtime'].get('error',''))
        value['runtime'].update(failure=failure,error=failure['message'])
    if value['runtime']['status']=='version_pending':value['runtime']['error']=''

    from . import environment_versions,tool_versions
    value['version_inventory']=environment_versions.inventory(value,tool_versions.builtins(),tool_versions.defaults(),tool_versions.latest_pointers(),tool_versions.read)
    return value


async def checked_summary(user,agent):
    try:return await run_in_threadpool(summary,user,agent)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc


@router.get('')
@require_permission('agents','read')
async def catalogue(request:Request,response:Response):
    user=get_effective_user_id();agents=await native_agents(request)
    from app.gateway.deps import is_admin_user
    can_import=await is_admin_user(request)
    response.headers['Cache-Control']='no-store'
    def load():
        entries=[];cache={}
        from . import environment_activity
        auth=getattr(request.state,'auth',None)
        activity=environment_activity.collect(user) if auth and auth.has_permission('threads','read') and runtimes.enabled() else {'observed':False,'jobs':[]}
        identity=runtimes.recipe([])[1]['core'] if runtimes.enabled() else None
        for agent in agents:
            try:entries.append(summary(user,agent,identity,cache))
            except ValueError as e:
                entries.append({'name':agent.name,'display_name':agent.display_name or agent.name,
                    'purpose':agent.description,'instructions':profiles.agent_instructions(user,agent), 'skills':agent.skills or [],'tools':[],
                    'deployment':profiles.preferences(user).get(agent.name,{'mode':'on_demand','ephemeral':False}),
                    'runtime':{'status':'invalid','error':str(e)}})
        for entry in entries:
            runtime=entry.get('runtime',{})
            entry['activity']=environment_activity.for_runtime(activity,runtime.get('id'),runtime.get('status') in preparation.ACTIVE,entry['name'])
        from .state import applications
        tool_names={'skill-'+a['id'] for a in applications()}
        inventory=[]
        for skill in profiles.skill_inventory(user):
            try:tools=profiles.skill_requirements(skill);error=''
            except ValueError as e:tools=[];error=str(e)
            inventory.append({'name':skill.name,'description':skill.description,'enabled':skill.enabled,
                              'category':str(skill.category),'kind':'tool' if skill.name in tool_names else 'method','tools':tools,'error':error})
        from .environment_transfers import for_user
        return {'transfers':for_user(user),'environments':entries,'presets':profiles.preset_catalog(),'skills':inventory,
                'dynamic':runtimes.enabled(),'core_preloaded':True,
                'preparation_serial':False,'parallelism':parallelism(),'activity':activity,'can_import_software':can_import,'can_configure_resources':can_import}
    try:return await run_in_threadpool(load)
    except (OSError,ValueError,RuntimeError) as e:raise HTTPException(409,str(e)[:500]) from e


def parallelism():
    from .docker_runtime import BUILD_LOCK,TERMINAL_LOCK
    from .runtime_settings import effective
    from .resource_budget import console_capacity
    limits=effective()
    from .resource_budget import BUDGET
    monitor=BUDGET.snapshot()
    builds=monitor['active']['build']
    with TERMINAL_LOCK.condition:terminals=TERMINAL_LOCK.active
    return {'limit':BUILD_LOCK.capacity(),'preparations':builds,'terminals':terminals,
        'terminal_limit':console_capacity(limits),'monitor':monitor}


@router.get('/resources/settings')
@require_permission('agents','read')
async def resources(request:Request,response:Response):
    from .runtime_settings import read
    response.headers['Cache-Control']='no-store'
    return await run_in_threadpool(read)


@router.put('/resources/settings')
@require_permission('agents','write')
async def configure_resources(value:RuntimeConfig,request:Request):
    from app.gateway.deps import is_admin_user
    from .runtime_settings import save
    same_origin(request)
    if not await is_admin_user(request):raise HTTPException(403,'Solo un amministratore può cambiare il budget condiviso')
    try:return await run_in_threadpool(save,value.model_dump())
    except ValueError as error:raise HTTPException(400,str(error)) from error


@router.post('/resources/rebalance')
@require_permission('agents','write')
async def rebalance_resources(request:Request):
    from app.gateway.deps import is_admin_user
    from .resource_budget import BUDGET
    same_origin(request)
    if not await is_admin_user(request):raise HTTPException(403,'Solo un amministratore può riassegnare il budget condiviso')
    result=await run_in_threadpool(BUDGET.rebalance)
    note=f" {result.get('memory_deferred',0)} allocazioni RAM restano superiori alla nuova ripartizione fino al rilascio." if result.get('memory_deferred') else ''
    return {**result,'message':f"Aggiornate {result['updated']} operazioni; {result['unchanged']} già allineate; {result['pending']} da verificare. La memoria attiva non viene ridotta."+note}


async def write_definition(value,request,create):
    user=get_effective_user_id();same_origin(request)
    try:
        resolved=await run_in_threadpool(profiles.resolve_skills,user,value.skills)
        if value.preload_tools is not None and set(value.preload_tools)-set(resolved['tools']):raise ValueError('Precarica soltanto strumenti delle skill selezionate')
        if set(value.tool_versions)-set(runtimes.closure(resolved['tools'])):raise ValueError('Scegli versioni solo degli strumenti selezionati nell’ambiente')
        if value.mode=='preload' and value.ephemeral:raise ValueError('Il predeploy non può essere temporaneo')
        from .tool_versions import check_selection
        check_selection(value.tool_versions)  # Validate before changing native configuration.
        from . import environment_history
        if not create:
            previous=await native_agent(request,value.name)
            environment_history.record(user,profiles.profile(user,previous))
        from app.gateway.routers.agents import AgentCreateRequest,AgentUpdateRequest,create_agent_endpoint,update_agent
        fields={'display_name':value.display_name,'description':value.purpose,'soul':value.instructions,'skills':resolved['skills']}
        if create:
            agent=await create_agent_endpoint(AgentCreateRequest(name=value.name,**fields),request)
        else:agent=await update_agent(value.name,AgentUpdateRequest(**fields),request)
        await run_in_threadpool(profiles.set_deployment,user,value.name,value.mode,value.ephemeral,value.preload_tools,value.tool_versions)
        environment_history.record(user,profiles.profile(user,agent))
        if value.mode=='preload' and runtimes.enabled():schedule(user,value.name,reschedule=True,trigger='configuration')
        return await run_in_threadpool(summary,user,agent)
    except ValueError as e:raise HTTPException(422,str(e)) from e


@router.post('/prepare-preloaded')
@require_permission('agents','write')
async def prepare_preloaded(request:Request):
    same_origin(request)
    agents=await native_agents(request);user=get_effective_user_id();names=[]
    for agent in agents:
        if profiles.preferences(user).get(agent.name,{}).get('mode')=='preload':
            schedule(user,agent.name);names.append(agent.name)
    return {'accepted':True,'environments':names}


@router.post('')
@require_permission('agents','write')
async def create(value:Definition,request:Request):
    return await write_definition(value,request,True)


@router.put('/{name}')
@require_permission('agents','write')
async def update(name:str,value:Definition,request:Request):
    if value.name!=name:raise HTTPException(422,'Identità dell’ambiente diversa dal percorso')
    return await write_definition(value,request,False)


@router.get('/{name}/export')
@require_permission('agents','read')
async def export(name:str,request:Request):
    from app.gateway.routers.agents import export_agent_package
    # Native export carries authoritative Agent configuration and skill references.
    response=Response()
    package=await export_agent_package(name,request,response)
    value=package.model_dump(mode='json')
    value['righaven_deployment']=profiles.preferences(get_effective_user_id()).get(name,{'mode':'on_demand','ephemeral':False})
    return Response(json.dumps(value,ensure_ascii=False),media_type='application/json',headers={
        'Cache-Control':'no-store','Content-Disposition':'attachment; filename="'+name+'-environment.json"'})


@router.post('/{name}/prepare',status_code=202)
@require_permission('agents','write')
async def prepare(name:str,request:Request):
    same_origin(request)
    if not runtimes.enabled():raise HTTPException(409,'Installa il Compose per ambienti dinamici prima della preparazione')
    agent=await native_agent(request,name)
    user=get_effective_user_id()
    value=await checked_summary(user,agent)
    schedule(user,name)
    return {'accepted':True,'environment':value}


def schedule(user,name,*,reschedule=False,refresh_versions=True,trigger='manual',trigger_tool=''):
    """Preparation outlives the HTTP connection; all writes retain the native owner."""
    key=(user,name)
    with runtimes._PREPARING_LOCK:
        if runtimes.STOPPING.is_set():return
        if key in runtimes.PREPARING:
            active=runtimes.PREPARATION_CONTROL[key]
            active['reschedule']|=reschedule or refresh_versions and not active.get('refresh_versions',True)
            active['refresh_versions']=active.get('refresh_versions',True) or refresh_versions
            return
        runtimes.PREPARING.add(key)
        control={'cancel':threading.Event(),'error':'','reschedule':False,'refresh_versions':refresh_versions,'trigger':trigger,'trigger_tool':trigger_tool}
        runtimes.PREPARATION_CONTROL[key]=control
    def work():
        try:
            from righaven_core.config.agents_config import load_agent_config
            from .capability_policy import native_policy
            from .docker_runtime import BUILD_LOCK as EXECUTION_LOCK
            from .resource_slot import PreparationCancel
            from .tool_versions import software_selections,resolved as resolve_versions
            agent=load_agent_config(name,user_id=user)
            if agent is None:return
            initial=profiles.resolve_skills(user,agent.skills)
            choice=software_selections(user,name,initial['tools'])
            from .environment_changes import reason
            preparation.begin(user,name,choice,reason(control['trigger'],control['trigger_tool']))
            pins=resolve_versions(choice,wait=True,cancel=control['cancel'],refresh=control['refresh_versions'],on_progress=lambda **fields:preparation.update(user,name,**fields))
            while not control['cancel'].is_set():
                yielded=threading.Event()
                control['state']='waiting_chat' if control.get('state')=='waiting_chat' or getattr(EXECUTION_LOCK,'foreground_waiters',0) or (hasattr(EXECUTION_LOCK,'waiting_info') and EXECUTION_LOCK.locked() and EXECUTION_LOCK.waiting_info()['queue_reason']=='work') else 'queued'
                preparation.update(user,name,phase=control['state'],environment_id='',tool='',version='',version_job_id='')
                try:
                    if control['cancel'].is_set():return
                    control['state']='preparing'
                    agent=load_agent_config(name,user_id=user)
                    if agent is None:return
                    resolved=profiles.resolve_skills(user,agent.skills)
                    policy=native_policy(user,name)
                    if set(resolved['tools'])-set(policy['allowed']):raise ValueError('Strumenti esclusi dal profilo')
                    prefs=profiles.preferences(user).get(name,{'mode':'on_demand'})
                    tools=profiles.preloaded_tools(prefs,resolved['tools']) if prefs.get('mode')=='preload' else resolved['tools']
                    from .capability_policy import require_tools
                    require_tools(policy,set(runtimes.closure(tools))-{'playwright'})
                    control['environment_id']=runtimes.recipe(tools,versions=pins)[0]
                    preparation.update(user,name,phase='preparing',environment_id=control['environment_id'],tool='',index=len(choice),total=len(choice))
                    ready=runtimes.ensure(tools,background=True,exact=True,cancel=PreparationCancel(control['cancel'],yielded),cache_dependencies=not prefs.get('ephemeral',False),versions=pins)
                    preparation.update(user,name,phase='ready',ready_id=ready['id'],environment_id=ready['id'],error='',failure={})
                    return
                except runtimes.PreparationDeferred:
                    control['state']='waiting_chat'
                    continue
                except runtimes.PreparationCleanupError as exc:
                    EXECUTION_LOCK.quarantine(str(exc))
                    raise

        finally:
            pass  # The guarded wrapper records failures before releasing admission.
    # Metadata records the real failure; exceptions must not become silent thread tracebacks.
    def guarded():
        try:work()
        except Exception as exc:
            control['error']=str(exc)[:500]
            saved=preparation.read(user,name);image_key=control.get('environment_id') or saved.get('environment_id')
            failure=(runtimes.read(image_key) or {}).get('failure') if image_key else None
            failure=failure or preparation.diagnosis(runtimes.preparation_text(image_key) if image_key else '',str(exc))
            preparation.update(user,name,phase='cancelled' if control['cancel'].is_set() else 'failed',error=failure['message'],failure=failure)
        finally:
            with runtimes._PREPARING_LOCK:
                runtimes.PREPARING.discard(key)
                again=control['reschedule']
            if again:schedule(user,name,refresh_versions=control['refresh_versions'],trigger=control['trigger'],trigger_tool=control['trigger_tool'])
    threading.Thread(target=guarded,daemon=True,name='environment-preparation').start()


def schedule_affected(tool):
    if tool.startswith('provider-'):return 0
    from righaven_core.config.paths import get_paths
    from righaven_core.config.agents_config import load_agent_config
    users=get_paths().base_dir/'users';count=0
    if not users.exists():return count
    for user in users.iterdir():
        if not user.is_dir() or user.is_symlink():continue
        for name,prefs in profiles.preferences(user.name).items():
            if prefs.get('mode')!='preload' or tool in prefs.get('tool_versions',{}):continue
            agent=load_agent_config(name,user_id=user.name)
            if agent is None:continue
            try:
                resolved=profiles.resolve_skills(user.name,agent.skills)
                tools=set(runtimes.closure(profiles.preloaded_tools(prefs,resolved['tools'])))
                if tool not in tools:continue
                schedule(user.name,name,reschedule=True,trigger='version_change',trigger_tool=tool);count+=1
            except (OSError,ValueError):continue
    return count


def preload_startup():
    if not runtimes.enabled():return
    from .environment_transfers import recover
    recover()
    from .tool_versions import recover_jobs
    recover_jobs()
    runtimes.STOPPING.clear()
    runtimes.reconcile()
    from righaven_core.config.paths import get_paths
    users=get_paths().base_dir/'users'
    if not users.exists():return
    for user in users.iterdir():
        if not user.is_dir() or user.is_symlink():continue
        try:
            from righaven_core.config.agents_config import load_agent_config
            for name,value in profiles.preferences(user.name).items():
                if value.get('mode')!='preload':continue
                try:
                    agent=load_agent_config(name,user_id=user.name)
                    if agent is None:continue
                    try:current=summary(user.name,agent)
                    except (OSError,ValueError,RuntimeError):
                        schedule(user.name,name,refresh_versions=False,trigger='startup');continue
                    runtime=current['runtime']
                    if runtime.get('status')=='ready':
                        preparation.update(user.name,name,phase='ready',ready_id=runtime.get('id',''),environment_id=runtime.get('id',''),
                                           selection=current.get('selected_versions',{}),error='',failure={})
                        continue
                    # A deploy restores missing programs; it is not an instruction
                    # to look for new upstream releases or invalidate ready images.
                    schedule(user.name,name,refresh_versions=False,trigger='startup')
                except Exception as error:
                    # Optional preload restoration must not take down every API
                    # or prevent other owners' valid environments from restoring.
                    from .progress import clean_summary
                    detail=clean_summary(str(error))
                    logging.getLogger(__name__).error('Environment preload restoration failed: %s',detail)
                    try:preparation.update(user.name,name,phase='failed',error='Ripristino automatico non riuscito: '+detail)
                    except (OSError,ValueError):pass
        except (OSError,ValueError):continue


@router.get('/{name}/log')
@require_permission('agents','read')
async def preparation_log(name:str,request:Request):
    agent=await native_agent(request,name)
    value=await checked_summary(get_effective_user_id(),agent)
    user=get_effective_user_id();record=preparation.read(user,name)
    key=record.get('environment_id') or value['runtime'].get('id')
    since=record.get('started_at') if (value.get('preparation') or {}).get('active') else None
    detail=await run_in_threadpool(runtimes.preparation_text,key,since=since) if key else ''
    observation=await run_in_threadpool(runtimes.preparation_observation,key,since=since)
    if value.get('configuration_change') and not (value.get('preparation') or {}).get('active'):
        observation={**observation,'phase':'configuration_changed','historical':True,'recent_output':'','waiting_on':None}
    if record.get('phase') in ('resolving_versions','checking_versions') and not record.get('environment_id'):
        observation['phase']='resolving_versions' if record.get('version_state')=='resolving' and record.get('version_operation')!='queued' else 'queued'
        if observation['phase']!='queued':observation.pop('waiting_on',None)
    return {'text':detail or preparation.text(user,name),'preparation':value.get('preparation'),
        'failure':value['runtime'].get('failure'),'observation':observation}


@router.delete('/{name}/cache')
@require_permission('agents','write')
async def clear_cache(name:str,request:Request):
    same_origin(request);agent=await native_agent(request,name)
    value=await checked_summary(get_effective_user_id(),agent)
    key=value['runtime'].get('id')
    if not key:return {'removed':False}
    try:
        from .docker_runtime import BUILD_LOCK as EXECUTION_LOCK
        admitted=EXECUTION_LOCK.acquire_maintenance() if hasattr(EXECUTION_LOCK,'acquire_maintenance') else EXECUTION_LOCK.acquire(blocking=False)
        if not admitted:raise ValueError('Squadra occupata: attendi la fine della fase attiva')
        try:return await run_in_threadpool(runtimes.evict,key)
        finally:EXECUTION_LOCK.release()
    except (ValueError,OSError) as e:raise HTTPException(409,str(e)) from e


@router.post('/{name}/cancel')
@require_permission('agents','write')
async def cancel_preparation(name:str,request:Request):
    same_origin(request)
    await native_agent(request,name)
    key=(get_effective_user_id(),name)
    with runtimes._PREPARING_LOCK:
        control=runtimes.PREPARATION_CONTROL.get(key)
        if key not in runtimes.PREPARING or not control:
            raise HTTPException(409,'Nessuna preparazione manuale di questo ambiente da annullare. Per un incarico usa Stop nella conversazione.')
        control['reschedule']=False
        control['cancel'].set()
        preparation.update(key[0],name,phase='cancelled',error='Annullamento richiesto; attendo il rilascio delle risorse.')
    return {'accepted':True}


@router.post('/{name}/software-export',status_code=202)
@require_permission('agents','write')
async def software_export(name:str,request:Request):
    same_origin(request)
    agent=await native_agent(request,name);user=get_effective_user_id()
    value=await checked_summary(user,agent)
    if value['runtime']['status']!='ready':raise HTTPException(409,'Prepara l’ambiente prima di esportare i programmi')
    from . import environment_transfers as transfers,environment_portability as portable
    record=await run_in_threadpool(runtimes.read,value['runtime']['id'])
    if not record:raise HTTPException(409,'La base vuota non contiene programmi da esportare')
    try:directory,job=await run_in_threadpool(transfers.create,user,name,'export')
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    transfers.update(directory,environment_id=record['id'])
    def advance(phase,message):transfers.update(directory,phase=phase,message=message)
    def build_export():
        import tarfile
        archive=portable.export_image(record,directory,on_progress=advance)
        with tarfile.open(archive,'r:') as package:manifest=json.load(package.extractfile('manifest.json'))
        transfers.update(directory,image_validated=True,image_bytes=manifest['image_bytes'],layer_count=manifest['layer_count'])
        return archive
    transfers.start(directory,build_export)
    return transfers.public(job)


@router.post('/{name}/software-import',status_code=202)
@require_permission('agents','write')
async def software_import(name:str,request:Request):
    same_origin(request)
    from app.gateway.deps import require_admin_user
    await require_admin_user(request,detail='L’importazione modifica la cache software condivisa e richiede un amministratore')
    agent=await native_agent(request,name);user=get_effective_user_id()
    value=await checked_summary(user,agent)
    from . import environment_transfers as transfers,environment_portability as portable
    try:directory,job=await run_in_threadpool(transfers.create,user,name,'import')
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    archive=directory/'upload.tar';size=0
    try:
        capacity=await run_in_threadpool(__import__('shutil').disk_usage,directory)
        maximum=min(portable.MAX_BYTES+64*1024**2,max(0,(capacity.free-512*1024**2)//4))
        with archive.open('wb') as output:
            async for chunk in request.stream():
                size+=len(chunk)
                if size>maximum:raise HTTPException(413,'Pacchetto troppo grande o spazio insufficiente sul server')
                await run_in_threadpool(output.write,chunk)
        def install():
            imported=portable.import_image(archive,directory,value['preloaded_tools'] if value['deployment']['mode']=='preload' else value['tools'],allowed_tools=value['tools'],
                on_progress=lambda phase,message:transfers.update(directory,phase=phase,message=message))
            prefs=profiles.preferences(user).get(name,{'mode':'on_demand','ephemeral':False})
            if prefs!=value['deployment']:raise ValueError('Programmi importati nella cache; il profilo è cambiato durante il trasferimento. Seleziona le versioni importate dalla configurazione.')
            pins={t:imported.get('versions',{}).get(t,'builtin') for t in imported['tools']}
            pins.update({t:r for t,r in imported.get('versions',{}).items() if not t.startswith('provider-')})
            profiles.set_deployment(user,name,prefs['mode'],prefs.get('ephemeral',False),prefs.get('preload_tools'),{**prefs.get('tool_versions',{}),**pins})
        transfers.start(directory,install)
        return transfers.public(job)
    except BaseException:
        await run_in_threadpool(transfers.update,directory,state='failed',message='Caricamento interrotto; riprova il trasferimento')
        archive.unlink(missing_ok=True)
        raise


@router.get('/transfers/{identifier}/status')
@require_permission('agents','write')
async def transfer_status(identifier:str,request:Request):
    from . import environment_transfers as transfers
    try:
        directory,value=await run_in_threadpool(transfers.read,get_effective_user_id(),identifier)
        return transfers.public(value,directory)
    except FileNotFoundError as exc:raise HTTPException(404,'Trasferimento non trovato') from exc


@router.get('/transfers/{identifier}/download')
@require_permission('agents','write')
async def transfer_download(identifier:str,request:Request):
    from . import environment_transfers as transfers
    from fastapi.responses import FileResponse
    try:directory,value=await run_in_threadpool(transfers.read,get_effective_user_id(),identifier)
    except FileNotFoundError as exc:raise HTTPException(404,'Trasferimento non trovato') from exc
    if value['kind']=='export' and value['state']=='ready' and value.get('image_validated') is not True:
        raise HTTPException(409,'Esportazione precedente non verificata: esporta nuovamente i programmi con la versione aggiornata')
    if value['kind']!='export' or value['state']!='ready':raise HTTPException(409,'Pacchetto non ancora disponibile')
    archive=directory/'environment.righaven-env.tar'
    if not archive.is_file() or archive.is_symlink():raise HTTPException(409,'Il pacchetto non è più disponibile: esporta nuovamente l’ambiente')
    return FileResponse(archive,media_type='application/x-tar',
        filename=value['name']+'.righaven-env.tar',headers={'Cache-Control':'no-store'})


class TerminalInput(BaseModel):
    text:str=Field(max_length=8192)


class TerminalOpen(BaseModel):
    client_id:str|None=Field(default=None,pattern='^[a-f0-9]{32}$')


@router.post('/{name}/terminal',status_code=201)
@require_permission('agents','write')
async def open_terminal(name:str,request:Request,value:TerminalOpen|None=None):
    same_origin(request)
    client_id=value.client_id if value else None
    agent=await native_agent(request,name);user=get_effective_user_id();value=await checked_summary(user,agent)
    if value['runtime']['status']!='ready':raise HTTPException(409,'Prepara i programmi prima di aprire il terminale')
    from . import environment_terminal as terminal
    from .capability_policy import native_policy
    try:
        policy=await run_in_threadpool(native_policy,user,name)
        return await run_in_threadpool(terminal.start,user,name,value,policy,client_id=client_id)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc


@router.post('/terminal-clients/{client_id}/close')
@require_permission('agents','write')
async def close_terminal_client(client_id:str,request:Request):
    import re
    same_origin(request)
    if not re.fullmatch(r'[a-f0-9]{32}',client_id):raise HTTPException(422,'Identità finestra non valida')
    from .environment_terminal import close_client
    await run_in_threadpool(close_client,get_effective_user_id(),client_id)
    return {'accepted':True}


async def terminal_session(identifier):
    from .environment_terminal import get
    try:return get(get_effective_user_id(),identifier)
    except FileNotFoundError as exc:raise HTTPException(404,'Terminale non trovato') from exc


@router.get('/terminals/{identifier}/status')
@require_permission('agents','write')
async def terminal_status(identifier:str,request:Request,after:int|None=Query(default=None,ge=0)):
    session=await terminal_session(identifier)
    return await run_in_threadpool(session.public,after,1 if after is not None else 0)


@router.post('/terminals/{identifier}/input')
@require_permission('agents','write')
async def terminal_input(identifier:str,value:TerminalInput,request:Request):
    same_origin(request)
    session=await terminal_session(identifier)
    try:await run_in_threadpool(session.write,value.text)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    return {'accepted':True}


@router.post('/terminals/{identifier}/close')
@router.delete('/terminals/{identifier}')
@require_permission('agents','write')
async def close_terminal(identifier:str,request:Request):
    same_origin(request)
    (await terminal_session(identifier)).cancelled.set()
    return {'accepted':True}


class TerminalSize(BaseModel):
    cols:int=Field(ge=2,le=1000)
    rows:int=Field(ge=2,le=500)


@router.post('/terminals/{identifier}/resize')
@require_permission('agents','write')
async def resize_terminal(identifier:str,value:TerminalSize,request:Request):
    same_origin(request)
    session=await terminal_session(identifier)
    try:await run_in_threadpool(session.resize,value.cols,value.rows)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    return {'accepted':True}


@router.get('/{name}/history')
@require_permission('agents','read')
async def configuration_history(name:str,request:Request):
    await native_agent(request,name)
    from . import environment_history
    return {'items':list(reversed(environment_history.read(get_effective_user_id(),name)))}


@router.post('/{name}/restore/{revision}')
@require_permission('agents','write')
async def restore_configuration(name:str,revision:str,request:Request):
    await native_agent(request,name)
    from . import environment_history
    previous=next((item for item in environment_history.read(get_effective_user_id(),name) if item['id']==revision),None)
    if not previous:raise HTTPException(404,'Configuration revision not found')
    return await write_definition(Definition(**previous['definition']),request,False)


class ShareDefinition(BaseModel):
    id:str=Field(pattern='^[a-z0-9][a-z0-9-]{1,63}$')
    version:str=Field(pattern='^[a-zA-Z0-9][a-zA-Z0-9.+-]{0,63}$')
    title_en:str=Field(min_length=1,max_length=120)
    description_en:str=Field(min_length=1,max_length=4000)
    title_it:str=Field(min_length=1,max_length=120)
    description_it:str=Field(min_length=1,max_length=4000)
    revision:str
    confirm:bool=False
    preview_hash:str=''


@router.post('/{name}/share')
@require_permission('agents','write')
async def share_environment(name:str,value:ShareDefinition,request:Request):
    same_origin(request)
    agent=await native_agent(request,name);user=get_effective_user_id()
    profile=await run_in_threadpool(profiles.profile,user,agent)
    if value.revision!=profile['revision']:raise HTTPException(409,'Environment changed; reopen the sharing preview')
    from . import environment_sharing,gallery
    try:
        manifest=environment_sharing.manifest(profile,user,value.id,value.version,value.title_en,value.description_en,value.title_it,value.description_it)
        import hashlib
        digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
        if not value.confirm:return {'manifest':manifest,'scope':'instance','revision':profile['revision'],'preview_hash':digest}
        if value.preview_hash!=digest:raise HTTPException(409,'Sharing preview changed; inspect it again before publishing')
        return gallery.publish_pack(manifest)
    except ValueError as error:raise HTTPException(422,str(error)) from error


@router.post('/{name}/inspect-versions')
@require_permission('agents','read')
async def inspect_versions(name:str,request:Request):
    same_origin(request);user=get_effective_user_id()
    value=await checked_summary(user,await native_agent(request,name))
    runtime=value['runtime']
    if runtime['status']!='ready':raise HTTPException(409,'Prepare the environment before inspecting installed software')
    def inspect():
        import subprocess,uuid
        from .docker_runtime import base_arguments,remove
        label='rh-inspect-'+uuid.uuid4().hex[:12]
        script="import json;from pathlib import Path;r=Path('/opt/righaven');v={x['id']:x['version'] for x in json.loads((r/'installed.json').read_text())};v.update({'provider-'+k:z for k,z in json.loads((r/'catalog.lock.json').read_text()).get('cli_runtimes',{}).items() if k in ('codex','claude')});a=r/'antigravity.lock.json';v.update({'provider-agy':json.loads(a.read_text())['version']} if a.exists() else {});print(json.dumps(v))"
        try:
            args=base_arguments(label)+['--network=none','--entrypoint','python3',runtime.get('image_id') or runtime['image'],'-c',script]
            result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=60)
            if result.returncode:raise ValueError('Cannot read the prepared software manifest; inspect preparation details')
            versions=json.loads(result.stdout)
            runtimes.save(runtime['id'],installed_versions=versions)
        finally:remove(label)
    try:await run_in_threadpool(inspect)
    except (ValueError,OSError) as error:raise HTTPException(409,str(error)) from None
    except subprocess.TimeoutExpired:raise HTTPException(409,'Version inspection timed out; retry or inspect preparation details') from None
    return await checked_summary(user,await native_agent(request,name))
