"""Start a new objective from retained results, without carrying old recipe gates."""
import copy
import json
from pathlib import Path
import uuid
from .acceptance import fingerprint
from .project_store import locked,load
from .project_skills import read_document,redact_memory
from .progress import utcnow,workspace_key
from .state import atomic_json


def signature(project,journey=None):
    return fingerprint({'id':(project or {}).get('id'),'updated_at':(project or {}).get('updated_at'),
                        'contract':((project or {}).get('acceptance') or {}).get('hash'),
                        'journey':(journey or {}).get('revision')})


def view(workspace):
    from .journeys import _load
    with locked(workspace) as folder:
        project=load(folder,workspace) or {};journey=_load(folder)
        return {'signature':signature(project,journey),'goal':project.get('brief',''),
                'current_project':project.get('id'),'scope':project.get('scope'),
                'guided':bool(journey),'product_path':project.get('product_path'),
                'can_change':bool(project) and not any(s['status']=='running' for s in project.get('steps',[]))}


def filter_requests(project,requests):
    """Old requests remain archived, never become requirements of a new objective."""
    scope=project.get('scope') or {}
    if not scope.get('goal'):return requests
    goal=scope['goal']
    boundaries=[i for i,text in enumerate(requests) if text.strip()==goal]
    if boundaries:return requests[boundaries[-1]:]
    prior=set(scope.get('previous_request_hashes',[]))
    return [goal,*[r for r in requests if r.strip()!=goal and fingerprint(r) not in prior]]


def redirect(workspace,goal,expected,turn='',requests=None):
    from .journeys import _load
    from .project_controls import operational_resume
    from .policy_workflow import GOVERNANCE
    if not isinstance(goal,str) or not goal.strip() or len(goal)>2000 or operational_resume(goal):
        raise ValueError('Describe a new objective within 2000 characters; continuation controls are not objectives')
    goal=goal.strip()
    if redact_memory(goal)!=goal:raise ValueError('Use Connections for credentials, never project answers')
    with locked(workspace) as folder:
        old=load(folder,workspace);journey=_load(folder)
        if not old:raise ValueError('Create a first project before evolving its result')
        scope=old.get('scope') or {}
        if scope.get('goal')==goal and (scope.get('transition_signature')==expected or turn and scope.get('source_turn')==turn):
            return {'changed':False,'project_id':old['id'],'scope':scope}
        if expected!=signature(old,journey):raise ValueError('The project changed; reload before choosing a new objective')
        if any(s['status']=='running' for s in old['steps']):raise ValueError('Wait for active work to finish before changing the objective')
        history=folder/'objective-history';history.mkdir(exist_ok=True)
        if history.is_symlink() or not history.resolve().is_relative_to(folder.resolve()):raise ValueError('Invalid objective history')
        previous_texts=list((old.get('acceptance') or {}).get('user_requests',[]))
        manifest=(old.get('acceptance') or {}).get('request_manifest')
        if manifest:previous_texts=[read_document(workspace,d) for d in json.loads(read_document(workspace,manifest))]
        previous_texts.extend(requests or [])
        files=[]
        for name in [old.get('product_path'),*[p for step in old['steps'] for attempt in step['attempts'] for p in attempt.get('output_files',[])]]:
            if not isinstance(name,str):continue
            path=Path(name)
            if path.is_absolute() and path.is_relative_to(Path(workspace).resolve()):name='/mnt/user-data/'+path.relative_to(Path(workspace).resolve()).as_posix()
            if name.startswith('/mnt/user-data/outputs/') and name not in files:files.append(name)
        parent={'id':old['id'],'goal':old.get('brief',''),'product_path':old.get('product_path'),
                'outcome':old.get('outcome'),'files':files[:80],'files_count':len(files),
                'snapshot':'/mnt/user-data/.righaven-project/objective-history/'+old['id']+'.json'}
        atomic_json(history/(old['id']+'.json'),{'project':old,'journey':journey})
        from .source_packages import digest
        parent['snapshot']={'path':parent['snapshot'],'sha256':digest(history/(old['id']+'.json'))}
        stamp=utcnow();scope={'id':uuid.uuid4().hex,'goal':goal,'source_turn':turn,'at':stamp,'transition_signature':expected,
                             'parent':parent,'ancestors':[*((old.get('scope') or {}).get('ancestors') or []),
                             {'id':old['id'],'goal':old.get('brief',''),'product_path':old.get('product_path')}],
                             'previous_request_hashes':list(dict.fromkeys([*((old.get('scope') or {}).get('previous_request_hashes') or []),*[fingerprint(r) for r in previous_texts]])),
                             'detached_journey':fingerprint(journey) if journey else (old.get('scope') or {}).get('detached_journey'),
                             'reference_recipe':copy.deepcopy(journey.get('recipe')) if journey else (old.get('scope') or {}).get('reference_recipe')}
        new={'id':uuid.uuid4().hex,'workspace_key':workspace_key(workspace),'brief':goal,'project_type':'custom',
             'created_at':stamp,'updated_at':stamp,'status':'clarifying','steps':[],'requirements':{},
             'governance':dict(GOVERNANCE),'scope':scope,
             'checkpoints':{'enabled':False,'source':'collaborative_objective'},
             'summary':'New objective; previous results and sources retained',
             'next_action':'Clarify consequential choices, reuse the retained sources and propose a proportionate method'}
        if old.get('connections'):
            new['connections']={**old['connections'],'write':[],'deferred':[],'updated_at':stamp}
            atomic_json(folder/'connection-selection.json',new['connections'])
        # Organization-mandatory policies are rebuilt normally for the new plan;
        # old recipe-specific sheets and passed checks cannot approve new work.
        atomic_json(folder/'project.json',new)
        if journey:(folder/'journey.json').unlink()
    from .brief import sync_acceptance
    sync_acceptance(workspace,[goal])
    from .audit_log import append
    append(workspace,'User','Project objective changed','completed',goal,context={'parent_project':parent['id'],'project_id':new['id']})
    return {'changed':True,'project_id':new['id'],'scope':scope}
