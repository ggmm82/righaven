"""Observed worker activity for one account; readiness and occupancy are distinct."""
import json
from pathlib import Path
from .progress import read_status, public_status, job_path, workspace_key, TERMINAL, JOB_ID


def collect(user):
    from righaven_core.config.paths import get_paths
    from .docker_runtime import docker
    from .environment_runtime import installation
    paths=get_paths();threads=paths.user_dir(user)/'threads'
    owners={}
    if threads.is_dir() and not threads.is_symlink():
        for thread in threads.iterdir():
            if not thread.is_dir() or thread.is_symlink():continue
            try:workspace=paths.sandbox_user_data_dir(thread.name,user_id=user)
            except ValueError:continue
            owners[workspace_key(workspace)]=(thread.name,workspace)
    try:
        identifiers=docker('ps','-aq','--filter','label=org.righaven.harness.installation='+installation()).splitlines()
        containers=json.loads(docker('inspect',*identifiers)) if identifiers else []
    except (OSError,ValueError,RuntimeError,__import__('subprocess').SubprocessError):
        return {'observed':False,'jobs':[]}
    jobs=[]
    for container in containers:
        labels=container.get('Config',{}).get('Labels') or {}
        owner=owners.get(labels.get('org.righaven.harness.workspace'))
        if not owner:continue  # No cross-account project names, even for administrators.
        thread,workspace=owner;name=container.get('Name','').lstrip('/')
        if not JOB_ID.fullmatch(name):
            # Foreground environment preparations use a separate container name.
            if labels.get('org.righaven.environment'):
                jobs.append({'thread_id':thread,'environment_id':labels['org.righaven.environment'],
                    'role':'Preparazione strumenti','summary':'Preparazione dei programmi richiesti dalla chat',
                    'phase':'preparing_environment','observed_running':bool(container.get('State',{}).get('Running'))})
            continue
        try:
            value=read_status(job_path(workspace,name))
            if value.get('workspace_key')!=workspace_key(workspace):continue
            status=public_status(value)
        except (OSError,ValueError):continue
        running=bool(container.get('State',{}).get('Running'))
        if not running and status['resources_reclaimed']:continue
        jobs.append({'thread_id':thread,'job_id':name,'environment_id':(status.get('environment') or {}).get('id'),
            'profile':status.get('environment_profile',''),'role':status['role_title'] or status['agent'],'summary':status['work_summary'] or status['summary'],
            'tools':(status.get('environment') or {}).get('assigned_tools') or (status.get('environment') or {}).get('tools') or [],
            'versions':(status.get('environment') or {}).get('versions') or {},
            'phase':status['phase'],'observed_running':running,'heartbeat_at':status['heartbeat_at'],
            'last_activity_at':status['last_activity_at'],'cleanup':status['phase'] in TERMINAL})
    from .environment_terminal import SESSIONS
    for session in list(SESSIONS.values()):
        if session.user==user and not session.closed:
            jobs.append({'terminal_id':session.id,'profile':session.profile,'environment_id':session.environment_id,'role':'Terminale web',
                'summary':'Console CLI aperta: '+session.profile,'phase':'terminal','cleanup':session.cancelled.is_set(),'observed_running':session.process.poll() is None})
    return {'observed':True,'jobs':jobs}


def for_runtime(activity,identifier,preparing=False,profile=None):
    jobs=[j for j in activity['jobs'] if identifier and j.get('environment_id')==identifier or profile and j.get('profile')==profile]
    return {'state':'unknown' if not activity['observed'] else 'busy' if jobs else 'preparing' if preparing else 'idle',
            'jobs':jobs}
