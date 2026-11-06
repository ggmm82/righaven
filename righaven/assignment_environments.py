"""Reopen assignment software through the ordinary account-owned terminal.

The Gateway snapshot contains configuration only. It never retains a worker,
credentials, prompts, connection grants, processes or unvalidated image layers.
"""
import json
from pathlib import Path
from . import state
from .progress import JOB_ID, job_path, read_status, workspace_key, clean_summary


def snapshot_path(workspace, job_id):
    if not JOB_ID.fullmatch(job_id):raise ValueError('Invalid assignment identifier')
    return state.STATE/'assignment-environments'/workspace_key(workspace)/(job_id+'.json')


def capture(workspace, job_id, skills, runtime):
    state.atomic_json(snapshot_path(workspace,job_id),{
        'skills':list(skills), 'environment_id':(runtime or {}).get('id'),
        'tools':(runtime or {}).get('tools',[]),
        'versions':{tool:(runtime or {}).get('versions',{}).get(tool,'builtin')
                    for tool in (runtime or {}).get('tools',[]) if not tool.startswith('provider-')},
    })


def configuration(user, workspace, job_id):
    from .capability_policy import native_policy, require_tools
    from .environments import resolve_skills
    status=read_status(job_path(workspace,job_id))
    if status.get('workspace_key')!=workspace_key(workspace):raise ValueError('Assignment does not belong to this conversation')
    source=snapshot_path(workspace,job_id)
    if source.is_symlink():raise ValueError('Invalid assignment configuration')
    if source.is_file():
        if source.stat().st_size>50000:raise ValueError('Invalid assignment configuration')
        saved=json.loads(source.read_text())
    else:
        # Earlier jobs have no trusted snapshot. Reconstruct only catalog skill
        # names and a verified software record; never consume paths or images
        # from the worker-writable progress file.
        environment=status.get('environment') or {}
        saved={'skills':['skill-'+t for t in environment.get('assigned_tools',environment.get('tools',[]))],
               'environment_id':environment.get('id'),'versions':{}}
    policy=native_policy(user)
    resolved=resolve_skills(user,saved['skills'])
    if resolved['disabled']:raise ValueError('Assignment skills are disabled; review the saved configuration first')
    require_tools(policy,resolved['tools'])
    title=clean_summary(status.get('role_title') or status.get('agent') or 'Assignment',64)
    definition={'name':'assignment-'+job_id.removeprefix('rh-job-'),'display_name':title,
        'purpose':clean_summary(status.get('work_summary') or status.get('summary') or title,4000),
        'instructions':'','skills':resolved['skills'],'mode':'on_demand','ephemeral':False,
        'preload_tools':None,'tool_versions':saved.get('versions',{})}
    return definition,saved,policy,status


def terminal_profile(user, workspace, job_id):
    from . import environment_runtime as runtime
    from .skill_composition import execution_policy
    definition,saved,policy,status=configuration(user,workspace,job_id)
    if not snapshot_path(workspace,job_id).is_file() and not (status.get('environment') or {}).get('id'):
        raise ValueError('Assignment software is not ready yet; wait for preparation to finish')
    identifier=saved.get('environment_id')
    record=runtime.read(identifier) if identifier else None
    if not record:
        identifier,spec=runtime.recipe([])
        if saved.get('tools') or definition['skills'] and any(s.removeprefix('skill-') in policy['allowed'] for s in definition['skills']):
            raise ValueError('Assignment software is no longer available; save the configuration and prepare it again')
        record={'id':identifier,'image_id':spec['core'],'base_only':True}
    if not record.get('base_only') and not runtime.image_exists(record):
        raise ValueError('Assignment software is no longer available; save the configuration and prepare it again')
    from .environments import resolve_skills
    tools=resolve_skills(user,definition['skills'])['tools']
    if not set(tools).issubset(record.get('tools',[])):
        raise ValueError('Assignment software does not contain the selected tools')
    policy=execution_policy({'composition_version':1},policy,tools)
    # Only Gateway-derived, confined read-only mounts enter the existing
    # terminal constructor. Staging is never promoted by a terminal session.
    output=state.STATE/'task-staging'/workspace_key(workspace)/job_id/'output'
    if output.is_symlink() or not output.resolve().is_relative_to(state.STATE.resolve()):
        raise ValueError('Invalid assignment output path')
    mounts=[(Path(workspace),'/workspace/project')]
    if output.is_dir():mounts.append((output,'/workspace/output'))
    return {**definition,'runtime':{'id':identifier},'_terminal_record':record,
            '_terminal_mounts':mounts,'_assignment':job_id},policy
