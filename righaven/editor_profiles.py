"""Server editors use ordinary account-owned Agent environments, not a second registry."""
import hashlib
import json
from pathlib import Path
from . import editor_catalog,editor_documents as documents,environments as profiles,state,tool_versions
from .project_store import locked


def bind(workspace,sid,allowed,name):
    with locked(workspace) as folder:
        root,value=documents.record(folder,sid,allowed)
        if value.get('environment_profile')!=name:
            value['environment_profile']=name;state.atomic_json(root/'session.json',value)


def mark(user,name,identifier,versions):
    with state.LOCK:
        prefs=profiles.preferences(user)
        prefs.setdefault(name,{'mode':'on_demand','ephemeral':True,'preload_tools':None,'tool_versions':versions,'editors':[]})['editor_for']=identifier
        state.atomic_json(profiles.preferences_path(user),prefs)


async def ensure(workspace,sid,user,request,allowed,terminal=False):
    from starlette.concurrency import run_in_threadpool
    from fastapi import HTTPException
    from .environment_routes import native_agents,write_definition,Definition
    value=await run_in_threadpool(documents.metadata,workspace,sid,allowed)
    definition=editor_catalog.editor(value['editor'],allowed)
    if definition['mode'] not in ('service','desktop') and not terminal:raise ValueError('This editor runs in the browser')
    if not definition['tool']:raise ValueError('Select an environment for this project terminal')
    agents=await native_agents(request);tool=definition['tool']
    selections=value.get('tool_versions') or {tool:'builtin'}
    identity=json.dumps([definition['id'],value.get('tool_versions',{}),value['editor_version'].removeprefix('v')],sort_keys=True)
    stem='editor-'+definition['id']+'-'+hashlib.sha256(identity.encode()).hexdigest()[:12]
    deployment=await run_in_threadpool(profiles.preferences,user)
    bound=value.get('environment_profile')
    for agent in agents:
        if agent.name==bound:
            scoped=await run_in_threadpool(profiles.profile,user,agent)
            if tool not in scoped['tools']:raise ValueError('The editor environment no longer enables this tool; update its skills before reopening')
            return agent.name
    # Prefer a user's prepared environment with the same pinned program release.
    for agent in agents:
        prefs=deployment.get(agent.name,{})
        scoped=await run_in_threadpool(profiles.profile,user,agent)
        if tool not in scoped['tools']:continue
        try:pins=await run_in_threadpool(tool_versions.resolved,tool_versions.software_selections(user,agent.name,[tool]),refresh=False)
        except ValueError:continue
        if pins!=value.get('tool_versions',{}):continue
        if prefs.get('editor_for')!=definition['id'] and agent.name!=stem:
            from .environment_runtime import available
            try:
                full_pins=await run_in_threadpool(tool_versions.resolved,tool_versions.software_selections(user,agent.name,scoped['tools']),refresh=False)
                ready=await run_in_threadpool(available,scoped['tools'],versions=full_pins)
            except (OSError,ValueError):continue
            if ready.get('status')!='ready':continue
        await run_in_threadpool(bind,workspace,sid,allowed,agent.name)
        return agent.name
    name=stem
    if any(agent.name==name for agent in agents):raise ValueError('The saved editor environment changed; review its configuration before reopening')
    desired=Definition(name=name,display_name=definition['name'],purpose='Edit documents with '+definition['name']+' and use its software from the terminal.',
        instructions='Keep each assignment and editing draft isolated. Preserve editable sources and portable assets.',
        skills=['skill-'+tool],mode='on_demand',ephemeral=True,tool_versions=selections)
    try:await write_definition(desired,request,True)
    except HTTPException as error:
        # Another tab may have registered the same exact environment concurrently.
        if error.status_code!=409:raise
        agents=await native_agents(request)
        candidate=next((a for a in agents if a.name==name),None)
        if candidate is None or tool not in profiles.profile(user,candidate)['tools']:raise
    await run_in_threadpool(mark,user,name,definition['id'],selections)
    await run_in_threadpool(bind,workspace,sid,allowed,name)
    return name


def remember(workspace,sid,allowed,user,software,interface_id):
    """Record verified runtime identity without changing the document revision."""
    with locked(workspace) as folder:
        root,value=documents.record(folder,sid,allowed)
        value.update(runtime_environment_id=software['id'],runtime_interface_id=interface_id)
        state.atomic_json(root/'session.json',value)
    name=value.get('environment_profile')
    if not name:return
    from .environment_preparation import update
    with state.LOCK:
        prefs=profiles.preferences(user)
        if prefs.get(name,{}).get('editor_for')!=value['editor']:return
        prefs[name].setdefault('editor_software',{})[value['editor']]={'environment_id':software['id'],'interface_id':interface_id}
        state.atomic_json(profiles.preferences_path(user),prefs)
    update(user,name,phase='ready',ready_id=software['id'],selection=prefs[name].get('tool_versions',{}))


async def recover(user,request,allowed):
    """Explicit, bounded migration of historical server drafts; never start programs."""
    from righaven_core.config.paths import get_paths
    from app.gateway.deps import get_thread_store
    from starlette.concurrency import run_in_threadpool
    paths=get_paths();threads=paths.user_dir(user)/'threads';names=set();visited=0;scanned=0;limited=False
    if not threads.is_dir() or threads.is_symlink():return {'environments':[],'limited':False}
    store=get_thread_store(request)
    for thread in threads.iterdir():
        scanned+=1
        if scanned>1000:limited=True;break
        if not thread.is_dir() or thread.is_symlink():continue
        if not await store.check_access(thread.name,user,require_existing=True):continue
        try:
            workspace=paths.sandbox_user_data_dir(thread.name,user_id=user)
            sessions=await run_in_threadpool(documents.listing,workspace,allowed)
        except (OSError,ValueError):continue
        for session in sessions:
            visited+=1
            if visited>2000:limited=True;break
            if editor_catalog.editor(session['editor'],allowed)['mode'] not in ('service','desktop'):continue
            names.add(await ensure(workspace,session['id'],user,request,allowed))
        if limited:break
    return {'environments':sorted(names),'limited':limited}
