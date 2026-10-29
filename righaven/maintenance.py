"""Bounded, owner-scoped reset previews with single-use confirmation tokens."""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,Field,ConfigDict
from righaven_core.runtime.user_context import get_effective_user_id
from .identity import current_user_id
from .router import same_origin
from . import state,environments
router=APIRouter(prefix='/api/harness/maintenance',tags=['Maintenance'])
SCOPES={'chats','environments','skill_overrides','personal_versions','models','global_versions'}


def directory(user):
    from righaven_core.config.paths import get_paths
    root=get_paths().user_dir(user)/'maintenance';root.mkdir(parents=True,exist_ok=True)
    return root


async def inventory(request):
    from app.gateway.routers.threads import search_threads,ThreadSearchRequest
    from .environment_routes import native_agents
    from app.gateway.deps import is_admin_user
    user=get_effective_user_id();threads=[]
    for offset in range(0,100000,1000):
        batch=await search_threads(ThreadSearchRequest(limit=1000,offset=offset),request)
        threads.extend({'id':item.thread_id,'label':getattr(item,'title',None) or item.metadata.get('title') or item.thread_id,'status':item.status,'revision':signature(item.model_dump(mode='json'))} for item in batch)
        if len(batch)<1000:break
    else:raise HTTPException(409,'Too many conversations for one reset; select smaller batches')
    agents=await native_agents(request)
    from righaven_core.skills.storage import get_or_new_user_skill_storage
    skills=get_or_new_user_skill_storage(user).load_skills(enabled_only=False)
    prefs=environments.preferences(user)
    return {'chats':threads,'environments':[{'id':agent.name,'label':agent.display_name or agent.name,'revision':signature(environments.profile(user,agent))} for agent in agents],
            'skill_overrides':[{'id':skill.name,'label':skill.name,'revision':signature({str(p.relative_to(skill.skill_dir)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(skill.skill_dir).rglob('*.md') if p.is_file() and not p.is_symlink()})} for skill in skills if str(skill.category)=='custom'],
            'personal_versions':[{'id':name,'label':name,'choices':pref['tool_versions']} for name,pref in prefs.items() if pref.get('tool_versions')],
            'can_reset_shared':await is_admin_user(request),
            'global_versions':[{'id':key,'label':key} for key in __import__('righaven.tool_versions',fromlist=['defaults']).defaults()] if await is_admin_user(request) else []}


@router.get('')
async def list_reset_targets(request:Request):
    current_user_id(request)
    return await inventory(request)


class Preview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scopes:list[str]=Field(min_length=1,max_length=6)
    targets:dict[str,list[str]]=Field(default_factory=dict)
    all_personal:bool=False


async def snapshot(body,request):
    available=await inventory(request)
    scopes=set(body.scopes)
    if body.all_personal:scopes|={'chats','environments','skill_overrides','personal_versions'}
    if scopes-SCOPES:raise HTTPException(422,'Unknown reset scope')
    if scopes&{'models','global_versions'} and not available['can_reset_shared']:raise HTTPException(403,'Shared configuration requires an administrator')
    selected={}
    for scope in sorted(scopes):
        if scope in ('models','global_versions'):
            from . import tool_versions
            selected[scope]=([{'id':name,'label':name,'profile':{key:value for key,value in state.team(name).items() if key in ('engine','model')}} for name in ('coordinator','squad')] if scope=='models' else [{'id':name,'label':name,'choice':choice} for name,choice in tool_versions.defaults().items()])
        else:selected[scope]=available[scope]
        if scope in body.targets:
            wanted=set(body.targets[scope]);found={item['id'] for item in selected[scope]}
            if wanted-found:raise HTTPException(404,'A reset target is not owned by this account or no longer exists')
            selected[scope]=[item for item in selected[scope] if item['id'] in wanted]
    return selected


def signature(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


@router.post('/preview')
async def preview(body:Preview,request:Request):
    same_origin(request);current_user_id(request)
    user=get_effective_user_id();selected=await snapshot(body,request)
    token=uuid.uuid4().hex;count=sum(len(items) for items in selected.values())
    phrase='RESET '+str(count)+' ITEMS'
    value={'id':token,'user':user,'expires_at':time.time()+600,'request':body.model_dump(),'targets':selected,'fingerprint':signature(selected),'phrase':phrase,'consumed':False}
    state.atomic_json(directory(user)/(token+'.json'),value)
    return {'id':token,'expires_at':value['expires_at'],'targets':selected,'count':count,'confirmation_phrase':phrase,
            'notice':'Conversations remove their messages and project data. Environments remove personal profiles and deployment choices, not shared prepared images. Skill reset removes personal overrides; shipped instructions reappear. Version reset restores default choices without deleting software. Accounts and provider credentials are preserved.'}


class Confirmation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern='^[a-f0-9]{32}$')
    phrase:str


async def apply_confirmation(body:Confirmation,request:Request):
    current_user_id(request);same_origin(request);user=get_effective_user_id()
    import fcntl
    path=directory(user)/(body.id+'.json')
    if not path.is_file():raise HTTPException(404,'Reset preview not found')
    # Cross-process reservation prevents two Gateway replicas from consuming a token.
    with path.open('r+') as lock:

        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise HTTPException(409,'A reset with this preview is already running') from None
        proposal=json.load(lock)
        if proposal['user']!=user or proposal['consumed'] or time.time()>proposal['expires_at']:raise HTTPException(409,'Preview expired or already used; create a new preview')
        if body.phrase!=proposal['phrase']:raise HTTPException(409,'Type the exact confirmation phrase')
        selected=await snapshot(Preview(**proposal['request']),request)
        if signature(selected)!=proposal['fingerprint']:raise HTTPException(409,'Targets changed after the preview; review a new preview')
        from .environment_activity import collect
        if collect(user).get('jobs'):raise HTTPException(409,'Finish or stop active work and close terminals before resetting')
        if any(key[0]==user for key in __import__('righaven.environment_runtime',fromlist=['PREPARING']).PREPARING):raise HTTPException(409,'Wait for environment preparations or cancel them before resetting')
        proposal['consumed']=True;lock.seek(0);json.dump(proposal,lock);lock.truncate();lock.flush()
    completed=[]
    try:
        for scope in ('chats','personal_versions','skill_overrides','environments','models','global_versions'):
            items=selected.get(scope,[])
            for item in items:
                identifier=item['id']
                if scope=='chats':
                    from app.gateway.routers.threads import delete_thread_data
                    await delete_thread_data(identifier,request)
                elif scope=='environments':
                    from app.gateway.routers.agents import delete_agent
                    await delete_agent(identifier,request)
                    with state.LOCK:
                        prefs=environments.preferences(user);prefs.pop(identifier,None);state.atomic_json(environments.preferences_path(user),prefs)
                elif scope=='skill_overrides':
                    from righaven_core.skills.storage import get_or_new_user_skill_storage
                    store=get_or_new_user_skill_storage(user);store.delete_custom_skill(identifier)
                elif scope=='personal_versions':
                    pref=environments.preferences(user)[identifier]
                    environments.set_deployment(user,identifier,pref['mode'],pref.get('ephemeral',False),pref.get('preload_tools'),{})
                elif scope=='global_versions':
                    from .tool_versions import activate
                    activate(identifier,'builtin')
                elif scope=='models':
                    import yaml
                    from .bootstrap import configure_team
                    defaults=yaml.safe_load((state.ROOT/'righaven.yaml').read_text())['models'][0]
                    configure_team('codex',defaults['model'],scope=identifier)
                completed.append({'scope':scope,'id':identifier})
        from righaven_core.agents.lead_agent.prompt import invalidate_user_skill_cache,publish_skills_cache_reset
        invalidate_user_skill_cache(user);publish_skills_cache_reset(user_id=user)
    except Exception as error:
        state.atomic_json(directory(user)/(body.id+'-result.json'),{'completed':completed,'error_type':type(error).__name__})
        raise HTTPException(409,{'message':'Reset stopped. Review completed operations before a new preview.','completed':completed,'reason':str(error)[:500]}) from None
    result={'completed':completed,'preserved':['accounts','provider_credentials','shared_prepared_software'],'finished_at':time.time()}
    state.atomic_json(directory(user)/(body.id+'-result.json'),result)
    return result


@router.post('/confirm')
async def confirm(body:Confirmation,request:Request):
    current_user_id(request);same_origin(request)
    import fcntl
    with (directory(get_effective_user_id())/'.operation.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise HTTPException(409,'Another reset is running in this account') from None
        try:return await apply_confirmation(body,request)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)
