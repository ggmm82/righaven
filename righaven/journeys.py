"""Persistent guided projects. Native plans own work; journeys own user decisions and gates."""
import copy
from functools import lru_cache
import json
from pathlib import Path
from . import recipes, state
from .acceptance import fingerprint
from .progress import utcnow
from .project_store import locked, artifact_path
from .source_packages import digest
from .project_skills import redact_memory

FIELDS = {'goal': 2000, 'source': 200, 'destination': 200, 'bi': 200, 'frequency': 400, 'notes': 2000}
# A phase is satisfied when the owner approves it or decides it is not needed for this project.
DONE = ('approved', 'skipped')
ACTIONS = ('approve', 'revise', 'skip', 'reopen', 'keep')


def definition(identifier, user_id=None):
    """A built-in recipe, or a user recipe visible to user_id, that has a guided workflow."""
    try:
        recipe = recipes.find(identifier, user_id)
    except ValueError:
        recipe = None
    if not recipe or not recipe.get('workflow'):
        raise ValueError('Unknown guided workflow')
    return recipe


def _load(folder):
    path = folder / 'journey.json'
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 200000:
        raise ValueError('Invalid guided project state')
    value = json.loads(path.read_text())
    # A new objective is authoritative even if a process stopped between saving
    # it and removing the old journey file. Newly selected recipes differ.
    project_path = folder / 'project.json'
    if project_path.exists():
        if project_path.is_symlink() or project_path.stat().st_size > 1000000:
            raise ValueError('Stato progetto non valido')
        scope = (json.loads(project_path.read_text()).get('scope') or {})
        if scope.get('detached_journey') == fingerprint(value):
            return None
    return value


def _answers(body):
    if not isinstance(body, dict) or set(body) - set(FIELDS):
        raise ValueError('Unknown guided project field')
    result = {}
    for key, limit in FIELDS.items():
        text = body.get(key, '')
        if not isinstance(text, str) or len(text) > limit:
            raise ValueError('Invalid field: ' + key)
        result[key] = text.strip()
    if redact_memory(result) != result:
        raise ValueError('Use Connections for credentials, never project answers')
    return result


def start(workspace, identifier, answers, expected_revision=0, recipe=None, connections=None, owner=None, uses=None, write=None, mode='complete'):
    """Save the owner's choices; connections picked in the intake are assigned to the task when its project starts."""
    recipe = recipe or definition(identifier)
    if mode not in ('complete', 'first_result'):
        raise ValueError('Unknown project approach')
    clean = _answers(answers)
    if connections is not None and (not isinstance(connections, list) or len(connections) > 10 or not owner
                                    or not all(isinstance(c, str) for c in connections)):
        raise ValueError('Invalid connections')
    if not clean['goal']:
        raise ValueError('Describe the desired outcome')
    with locked(workspace) as folder:
        previous = _load(folder)
        if previous:
            if previous.get('mode', 'complete') != mode:
                raise ValueError('An existing task keeps its selected approach; start a new task to change it')
            if previous['recipe_id'] != identifier:
                raise ValueError('This task already has a guided workflow')
            if previous['answers'] == clean and (connections is None or (previous.get('connections') or {}).get('ids') == connections):
                return view(workspace, previous)  # Idempotent retry after a lost save response.
            if previous['revision'] != expected_revision:
                raise ValueError('Guided project changed; reload before saving')
            value = copy.deepcopy(previous)
            value['answers'] = clean
            for stage in value['stages']:
                if stage['status'] not in ('pending', 'skipped'):
                    stage['status'] = 'stale'
        else:
            if expected_revision != 0:
                raise ValueError('Guided project changed; reload before saving')
            from .outcome_workflow import definition as outcome_definition
            workflow = recipe['workflow'] if mode == 'complete' else outcome_definition()
            value = {'recipe_id': identifier, 'recipe_version': recipe['workflow']['version'], 'mode': mode,
                     'recipe': {'title': recipe['it']['title'], 'skills': recipes.skills_of(recipe), 'environment': recipe.get('environment'),
                                'tools': list(recipe['tools']), 'custom': bool(recipe.get('owner')),
                                'outputs': {'it': list(recipe['it']['outputs']), 'en': list(recipe['en']['outputs'])}},
                     'definition': copy.deepcopy(workflow), 'answers': clean, 'created_at': utcnow(),
                     'revision': 0, 'stages': [{'id': s['id'], 'status': 'pending', 'evidence': [], 'steps': [], 'note': ''}
                                               for s in workflow['stages']]}
            if mode == 'first_result':
                value['recipe']['outputs'] = {
                    'it': ['Il risultato richiesto: '+clean['goal'], 'Sorgenti modificabili, verifiche e istruzioni essenziali'],
                    'en': ['The requested result: '+clean['goal'], 'Editable sources, verification and concise instructions']}
        if connections is not None:
            ids = list(dict.fromkeys(connections))
            uses = {k: v for k, v in (uses or {}).items() if k in ids and v in ('source', 'destination')}
            # The owner says what each connection is for; a destination they allow writing to carries that consent.
            value['connections'] = {'owner': str(owner), 'ids': ids, 'uses': uses, 'write': [c for c in (write or []) if uses.get(c) == 'destination']}
        _save(folder, value)
    return view(workspace, value)


def _save(folder, value):
    value['revision'] += 1
    value['updated_at'] = utcnow()
    state.atomic_json(folder / 'journey.json', value)


def simplify(workspace, expected_revision):
    """Owner-only approach change, retaining artifacts, requirements and prior decisions."""
    from .outcome_workflow import definition as outcome_definition
    from .project_store import load
    with locked(workspace) as folder:
        old=_load(folder)
        if not old or old['revision']!=expected_revision:
            raise ValueError('Guided project changed; reload before deciding')
        if old.get('mode')=='first_result':
            return view(workspace,old)
        project=load(folder,workspace)
        if project and any(s['status']=='running' for s in project['steps']):
            raise ValueError('Wait for active work to finish before changing the approach')
        history=folder/'journey-history';history.mkdir(exist_ok=True)
        if history.is_symlink() or not history.resolve().is_relative_to(folder.resolve()):
            raise ValueError('Invalid guided project state')
        state.atomic_json(history/(str(old['revision'])+'.json'),old)
        value=copy.deepcopy(old)
        value['mode']='first_result';value['definition']=outcome_definition()
        value['previous_paths']=[*(old.get('previous_paths') or []),
            {'at':utcnow(),'mode':old.get('mode','complete'),'stages':[{'id':s['id'],'status':s['status'],
             'title':next((spec['title'] for spec in old['definition']['stages'] if spec['id']==s['id']),{'it':s['id'],'en':s['id']})} for s in old['stages']]}][-10:]
        value['stages']=[{'id':s['id'],'status':'pending','evidence':[],'steps':[],'note':''} for s in value['definition']['stages']]
        value.setdefault('recipe',{'title':value['recipe_id'],'skills':[],'environment':None})
        value['recipe']['outputs']={'it':['Il risultato richiesto: '+value['answers']['goal'],'Sorgenti modificabili e verifiche'],
                                    'en':['The requested result: '+value['answers']['goal'],'Editable sources and verification']}
        if project:
            for step in project['steps']:
                if step.get('phase_id'):
                    step['previous_phase_id']=step.pop('phase_id')
            policy=project.get('policy_plan')
            if policy:
                policy['sheets']=[s for s in policy['sheets'] if s.get('source_recipe')!=value['recipe_id']]
                policy['hash']=fingerprint({'sheets':policy['sheets']})
            state.atomic_json(folder/'project.json',project)
        _save(folder,value)
        return view(workspace,value)


@lru_cache(maxsize=512)
def _cached_digest(filename, metadata):
    return digest(Path(filename))


def _file_digest(path):
    stat=path.stat()
    key=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
    value=_cached_digest(str(path),key)
    after=path.stat()
    return value if key==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) else None


def verified_package(workspace, evidence):
    """Only a host-owned verification job may establish package execution evidence."""
    from .progress import JOB_ID, job_path, read_status
    from .project_store import workspace_path
    for item in evidence:
        path=artifact_path(workspace,item['path'])
        if not path or path.name!='package-check.json' or not JOB_ID.fullmatch(path.parent.name):
            continue
        expected=Path(workspace).resolve()/'outputs/workspace'/path.parent.name/'package-check.json'
        if path.resolve()!=expected or path.stat().st_size>200000:
            continue
        try:
            status=read_status(job_path(workspace,path.parent.name))
            report=json.loads(path.read_text())
            if status.get('engine')!='verification' or status.get('model')!='exported-package' or status.get('phase')!='completed' or report.get('status')!='passed':
                continue
            package=workspace_path(workspace,report['package'])
            if not package or not package.resolve().is_relative_to(Path(workspace).resolve()/'outputs'):
                continue
            files={p.relative_to(package).as_posix():_file_digest(p) for p in package.rglob('*') if p.is_file() and not p.is_symlink()}
            if files==report.get('files'):
                return True
        except (OSError,ValueError,KeyError,TypeError):
            continue
    return False


def _fresh(workspace, stage):
    try:
        fresh=bool(stage['evidence']) and all(
            (p := artifact_path(workspace, e['path'])) and _file_digest(p) == e['sha256'] for e in stage['evidence'])
        return fresh and (stage['id']!='package' or verified_package(workspace,stage['evidence']))
    except OSError:
        return False


def view(workspace, value=None):
    if value is None:
        with locked(workspace) as folder:
            value = _load(folder)
    if value is None:
        return None
    result = copy.deepcopy(value)
    by_id = {s['id']: s for s in result['stages']}
    for spec in result['definition']['stages']:
        stage = by_id[spec['id']]
        stage.update(title=spec['title'], outcome=spec['outcome'], depends_on=spec['depends_on'])
        if stage['status'] in ('review', 'approved') and not _fresh(workspace, stage):
            stage['status'] = 'stale'
        stage['gate'] = spec.get('gate', True)
        if any(by_id[d]['status'] not in DONE for d in spec['depends_on']):
            if stage['status'] not in ('pending', 'skipped'):
                stage['status'] = 'stale'
        stage['available'] = all(by_id[d]['status'] in DONE for d in spec['depends_on'])
    result['complete'] = all(s['status'] in DONE for s in result['stages'])
    result['current'] = next((s['id'] for s in result['stages'] if s['status'] not in DONE and s['available']), None)
    result['awaiting_owner'] = [s['id'] for s in result['stages'] if (s['available'] and s['status'] == 'review') or (s.get('proposal') and s['status'] not in DONE)]
    result['connections_optional'] = True
    return result


def record(workspace, stage_id, evidence, steps, note, expected_revision, propose_skip=False):
    """Coordinator submits existing artifacts for owner approval, or proposes skipping a phase; it cannot approve or skip."""
    if not isinstance(note, str) or not 5 <= len(note.strip()) <= 1500 or redact_memory(note) != note:
        raise ValueError('Describe the result without credentials')
    if not isinstance(evidence, list) or not 0 <= len(evidence) <= 12 or not all(isinstance(p, str) for p in evidence):
        raise ValueError('Attach at most twelve actual result files; empty starts a phase')
    if not isinstance(steps, list) or len(steps) > 12 or not all(isinstance(s, str) for s in steps):
        raise ValueError('Invalid activity references')
    with locked(workspace) as folder:
        raw = _load(folder)
        if not raw or raw['revision'] != expected_revision:
            raise ValueError('Guided project changed; read it again')
        value = view(workspace, raw)
        stage = next((s for s in value['stages'] if s['id'] == stage_id), None)
        if not stage or (not stage['available'] and not propose_skip):
            raise ValueError('Approve prerequisite results before this phase')
        if propose_skip:
            if stage['status'] in DONE:
                raise ValueError('This phase is already settled')
            target = next(s for s in raw['stages'] if s['id'] == stage_id)
            target['proposal'] = {'action': 'skip', 'reason': note.strip(), 'at': utcnow()}
            _save(folder, raw)
            return view(workspace, raw)
        from .project_store import load
        project = load(folder, workspace) or {}
        if not steps or not set(steps).issubset({s['id'] for s in project.get('steps', [])}):
            raise ValueError('Link this phase to actual native project activities')
        if evidence and stage.get('gate', True):
            _require_review(project, steps, stage_id)
        if evidence and not stage['depends_on']:
            _require_sources(raw, project)
            _require_destination_result(workspace,raw,project)
        kept = []
        for filename in evidence:
            path = artifact_path(workspace, filename)
            if not path or path.is_relative_to(folder):
                raise ValueError('Evidence must be a saved project artifact')
            kept.append({'path': '/mnt/user-data/' + path.relative_to(Path(workspace).resolve()).as_posix(), 'sha256': digest(path)})
        if stage_id=='package' and kept and not verified_package(workspace,kept):
            raise ValueError('Run harness_package_check on this exact package and attach its successful verification report')
        target = next(s for s in raw['stages'] if s['id'] == stage_id)
        gated = stage.get('gate', True)
        # Phases the recipe author marked without approval complete with their evidence; the owner can still reopen them.
        target.update(status=('review' if gated else 'approved') if kept else 'working', evidence=kept, steps=steps, note=note.strip())
        target.pop('proposal', None)
        if kept and not gated:
            target.update(decision_at=utcnow(), decision='automatic')
        _invalidate(raw, stage_id)
        _save(folder, raw)
    return view(workspace, raw)


def _require_sources(journey, project):
    sources = [c for c, use in ((journey.get('connections') or {}).get('uses') or {}).items() if use == 'source']
    declared = {c for role in project.get('roles', []) for c in role.get('connections', [])}
    if set(sources) - declared:
        raise ValueError('Read the source connections the owner chose in this phase: declare them in roles_json connections: ' + ', '.join(sorted(set(sources) - declared)))
    from .connection_outcomes import destinations
    missing=set(destinations(project))-declared
    if missing:
        raise ValueError('Plan a role for the requested destinations; declare them in roles_json connections: '+', '.join(sorted(missing)))


def _require_destination_result(workspace,journey,project):
    # A full pipeline can legitimately begin with cataloging. A first usable
    # result cannot omit the external system the owner explicitly requested.
    if journey.get('mode')=='first_result':
        from .connection_outcomes import require_complete
        require_complete(workspace,project)


def _require_review(project, steps, stage_id=None):
    """The owner decides on reviewed results: the independent review of the phase must have finished first."""
    by_id = {s['id']: s for s in project.get('steps', [])}
    work = [sid for sid in steps if by_id[sid].get('purpose') != 'review']
    produced = max([a.get('finished_at') or '' for sid in work for a in by_id[sid].get('attempts', [])] or [''])
    reviews = [s for s in project.get('steps', []) if s.get('purpose') == 'review'
               and (s.get('phase_id') == stage_id or set(s.get('depends_on', [])) & set(work)
                    or (s.get('status')=='completed' and not s.get('phase_id') and not s.get('depends_on')))]
    if any(s['status'] in ('pending', 'running') for s in reviews):
        raise ValueError('Wait for the running quality review to finish before submitting this phase to the owner')
    if not any(s['status'] == 'completed' and ((s.get('attempts') or [{}])[-1].get('finished_at') or '') >= produced
               and ((s.get('attempts') or [{}])[-1].get('quality_review') or {}).get('status', 'passed') == 'passed'
               and not (s.get('role_id') and s.get('role_id') in {by_id[sid].get('role_id') for sid in work}) for s in reviews):
        raise ValueError('Run the independent quality review of this phase before submitting it to the owner')


def begin_activity(workspace, stage_id, step_id):
    """An explicit assignment phase binds/starts it atomically; never approves a gate."""
    from .project_store import load
    with locked(workspace) as folder:
        raw = _load(folder)
        if not raw:
            raise ValueError('This task has no guided path')
        value = view(workspace, raw)
        stage = next((s for s in value['stages'] if s['id']==stage_id), None)
        if not stage or stage_id != value['current'] or not stage['available'] or stage['status']=='review':
            raise ValueError('This phase is not available for work; wait for the owner decision')
        project = load(folder, workspace) or {}
        step = next((s for s in project.get('steps', []) if s['id']==step_id), None)
        if not step or (step.get('phase_id') and step['phase_id'] != stage_id):
            raise ValueError('Select an existing activity belonging to this phase')
        target = next(s for s in raw['stages'] if s['id']==stage_id)
        if step_id not in target['steps']:
            target['steps'].append(step_id)
        if target['status']!='working' or step.get('status')!='completed':
            target.setdefault('activity_started_at', {})[step_id]=utcnow()
        target['status']='working'
        step['phase_id']=stage_id
        state.atomic_json(folder/'project.json', project)
        _save(folder, raw)


def reconcile(workspace):
    """Recorded, reviewed activities publish the current phase without an LLM state rewrite."""
    from .project_store import load
    with locked(workspace) as folder:
        raw = _load(folder)
        if not raw:
            return None
        value = view(workspace, raw)
        stage = next((s for s in value['stages'] if s['id']==value['current']), None)
        if not stage or stage['status']!='working' or not stage['steps']:
            return value
        project = load(folder, workspace) or {}
        if not stage['depends_on']:
            try:
                _require_sources(raw, project)
                _require_destination_result(workspace,raw,project)
            except ValueError as error:
                value['coordination_issue'] = str(error)
                return value
        by_id = {s['id']: s for s in project.get('steps', [])}
        selected = [by_id[sid] for sid in stage['steps'] if sid in by_id]
        if len(selected)!=len(stage['steps']) or any(s['status']!='completed' for s in selected):
            return value
        if stage.get('gate', True):
            try:
                _require_review(project, stage['steps'], stage['id'])
            except ValueError as error:
                value['coordination_issue'] = str(error)
                return value
        files = []
        for step in selected:
            latest=(step.get('attempts') or [{}])[-1]
            if (latest.get('started_at') or '') < stage.get('activity_started_at', {}).get(step['id'], ''):
                return value
            if latest.get('stale_request') or latest.get('failed_checks'):
                return value
            # A real failed quality verdict never becomes an owner approval candidate.
            if (latest.get('quality_review') or {}).get('status', 'passed')!='passed':
                return value
            for filename in latest.get('output_files', []):
                p=artifact_path(workspace,filename)
                if p and not p.is_relative_to(folder):
                    files.append({'path':'/mnt/user-data/'+p.relative_to(Path(workspace).resolve()).as_posix(),'sha256':digest(p)})
        kept=list({f['path']:f for f in files}.values())[:12]
        if not kept or (stage['id']=='package' and not verified_package(workspace,kept)):
            return value
        target=next(s for s in raw['stages'] if s['id']==stage['id'])
        target.update(status='review' if stage.get('gate',True) else 'approved', evidence=kept,
                      note=stage['outcome']['it'], automatic_submission=True)
        _invalidate(raw,stage['id'])
        _save(folder,raw)
        return view(workspace,raw)


def _invalidate(value, identifier):
    affected = {identifier}
    for spec in value['definition']['stages']:
        if set(spec['depends_on']) & affected:
            affected.add(spec['id'])
            stage = next(s for s in value['stages'] if s['id'] == spec['id'])
            if stage['status'] not in ('pending', 'skipped'):  # an owner skip stays a decision until reopened
                stage['status'] = 'stale'


def decide(workspace, stage_id, approve=None, expected_revision=0, note='', action=None):
    """Owner decision: approve, ask for corrections, skip a phase not needed, reopen a skipped one, or keep a phase the team proposed to skip."""
    action = action or ('approve' if approve is True else 'revise' if approve is False else None)
    if action not in ACTIONS or not isinstance(note, str) or len(note) > 1500 or redact_memory(note) != note:
        raise ValueError('Invalid decision')
    with locked(workspace) as folder:
        raw = _load(folder)
        if not raw or raw['revision'] != expected_revision:
            raise ValueError('Guided project changed; reload before deciding')
        current = view(workspace, raw)
        stage = next((s for s in current['stages'] if s['id'] == stage_id), None)
        # The owner may skip a later phase in advance; approvals need the results of earlier phases.
        if not stage or (not stage['available'] and action not in ('skip', 'keep')):
            raise ValueError('This result is not available for approval')
        if action in ('approve', 'revise') and stage['status'] not in ('review', 'approved'):
            raise ValueError('This result is not available for approval')
        if action == 'skip' and stage['status'] in DONE:
            raise ValueError('This phase is already settled')
        if action == 'reopen' and stage['status'] != 'skipped':
            raise ValueError('Only a skipped phase can be reopened')
        target = next(s for s in raw['stages'] if s['id'] == stage_id)
        if action == 'keep':
            if not target.pop('proposal', None):
                raise ValueError('No proposal to answer for this phase')
            target.update(decision_note=note, decision='keep', decision_at=utcnow())
            _save(folder, raw)
            return view(workspace, raw)
        status = {'approve': 'approved', 'revise': 'blocked', 'skip': 'skipped', 'reopen': 'pending'}[action]
        target.update(status=status, decision_at=utcnow(), decision_note=note, decision=action)
        target.pop('proposal', None)
        _invalidate(raw, stage_id)
        _save(folder, raw)
    return view(workspace, raw)


def decide_many(workspace, stage_ids, action, expected_revision, note=''):
    """One owner answer to several skip proposals, e.g. every phase a demo does not need."""
    if action not in ('skip', 'keep') or not isinstance(stage_ids, list) or not 1 <= len(stage_ids) <= 12:
        raise ValueError('Invalid decision')
    value = None
    revision = expected_revision
    for stage_id in stage_ids:
        value = decide(workspace, stage_id, None, revision, note, action)
        revision = value['revision']
    return value


def outcome_seed(journey, locale='it'):
    """The owner's own goal is the project's result; the recipe outputs describe the delivery."""
    answers = journey['answers']
    recipe = journey.get('recipe') or {}
    outputs = (recipe.get('outputs') or {}).get(locale) or []
    labels = {'source': 'Sorgenti', 'destination': 'Destinazione', 'bi': 'Report e BI', 'frequency': 'Frequenze', 'notes': 'Indicazioni'}
    return {'title': (recipe.get('title') or '')[:120], 'result': answers['goal'][:2000],
            'format': ('; '.join(outputs) or 'Risultati delle fasi del percorso guidato')[:500],
            'constraints': [(labels[k] + ': ' + answers[k])[:600] for k in labels if answers.get(k)][:8]}


def attach_policy(workspace, plan):
    """Pin shipped recipe policy only on an opted-in project, without changing the organization book."""
    journey = view(workspace)
    return pin_policy(plan, journey) if journey else plan


def pin_policy(plan, journey):
    policy = journey['definition'].get('policy')
    if not policy:  # user recipes carry their phases and gates, not an organization policy sheet
        return plan
    from .policy_book import validate_sheet, revision
    sheet = validate_sheet(policy)
    from .policy_book import book
    # Never replace an organization policy, including a previously imported recipe template.
    reserved={s['id'] for s in book()}
    base=sheet['id']
    suffix=0
    while sheet['id'] in reserved:
        suffix+=1
        sheet['id']=base[:34]+'_'+str(suffix)
    sheet.update(revision=revision(sheet), reason='Selected guided workflow', steps=[], source_recipe=journey['recipe_id'])
    plan = copy.deepcopy(plan)
    plan['sheets'] = [s for s in plan['sheets'] if s.get('source_recipe') != journey['recipe_id']] + [sheet]
    plan['hash'] = fingerprint({'sheets': plan['sheets']})
    return plan


def with_recipe_skills(roles, journey, enabled):
    """Recipe expertise guides coordination; each role opts into relevant skills.

    Injecting an end-to-end recipe into every specialist also injects its tool
    dependencies and deliverable checklist, even for a small unrelated phase.
    Explicit choices still pass normal native capability validation.
    """
    return [copy.deepcopy(role) for role in roles]


def next_action(value):
    if value.get('coordination_issue'):
        return {'action':'repair_phase_contract','phase_id':value['current'],'instruction':value['coordination_issue']}
    if value.get('awaiting_owner'):
        return {'action':'await_owner','phase_ids':value['awaiting_owner'], 'instruction':'Present the reviewed result and stop. The owner decides once in the task card; do not ask for approval in chat.'}
    if value['complete']:
        return {'action':'validate_delivery','instruction':'Validate the final result and present its editable sources. Learning is deferred.'}
    phase=next((s for s in value['stages'] if s['id']==value['current']),None)
    return {'action':'work_on_phase','phase_id':value['current'],'activity_ids':phase.get('steps',[]) if phase else [],
            'instruction':'Use harness_delegate with phase_id and an existing planned step_id. The runtime starts the phase and submits completed, independently reviewed results automatically. Do not set activity statuses to running or rewrite phase states.'}


def compact(value):
    """What the coordinator needs each turn: choices, phase states and evidence paths, without the full definition and policy."""
    if not value:
        return None
    recipe = {k: v for k, v in (value.get('recipe') or {}).items() if k != 'outputs'}
    return {'recipe_id': value['recipe_id'], 'mode': value.get('mode', 'complete'), **({'recipe': recipe} if recipe else {}),
            **({'coordination_issue':value['coordination_issue']} if value.get('coordination_issue') else {}),
            'revision': value['revision'], 'answers': value['answers'], 'current': value['current'],
            'complete': value['complete'], 'awaiting_owner': value.get('awaiting_owner', []),
            'next_action': next_action(value),
            'connections': [{'id': c, 'use': ((value.get('connections') or {}).get('uses') or {}).get(c, 'unspecified'),
                             'write': c in ((value.get('connections') or {}).get('write') or [])} for c in (value.get('connections') or {}).get('ids', [])],
            'stages': [{'id': s['id'], 'title': s['title']['it'], 'outcome': s['outcome']['it'], 'status': s['status'], 'available': s['available'],
                        'gate': s.get('gate', True), 'note': s.get('note', '')[:240 if s['id']==value['current'] else 80],
                        'evidence': [e['path'] for e in s.get('evidence', [])[:8 if s['id']==value['current'] else 2]],
                        **({'proposal': s['proposal']} if s.get('proposal') else {}), **({'decision_note': s['decision_note'][:400]} if s.get('decision_note') else {})}
                       for s in value['stages']]}


def instructions(workspace):
    value = view(workspace)
    if not value:
        return ''
    return ('\nGuided project (persisted owner choices): ' + json.dumps(compact(value), ensure_ascii=False) +
            '\nRead the attachments first. Ask at most three decisive unknowns, with recommendations. '
            'Connections are optional only when the owner did not request an external system. A selected destination with writing authorized is part of the requested result; never replace it with a local database without an explicit owner deferral. '
            'Compose dynamic roles and use authorized skills/environments for the current outcome. '
            'Use phase_id on harness_delegate to bind and start planned work. The runtime submits completed phase results after independent review; only the owner approves gates. Manual harness_journey remains available for explicit corrections. Include editable sources in the first useful result; do not repackage or repeat checks solely to relabel an unchanged approved result as final. '
            'Submit a gated phase only after its independent quality review has finished, so the owner decides on reviewed results; '
            'phases with gate=false complete when their evidence is recorded. '
            + (value['definition'].get('guidance') or '') + (' ' if value['definition'].get('guidance') else '') +
            'Do not ask the user to write SQL, JSON, YAML or CLI commands. '
            'The latest explicit owner requests and the agreed current project outcome define the result. answers.goal is the original intake, not an instruction to undo later owner revisions. Keep the original choices as history; update activity goals, roles and dependencies for the current revision, preserve reusable outputs and explicitly skip obsolete pending activities. Say in one sentence how the current phase moves toward the current result. '
            'Only the owner approves, asks for corrections or skips a phase, with the buttons in the project card above the chat '
            '(«Approva fase», «Chiedi correzioni», «Salta fase»). Never use ask_clarification or a chat question to approve, confirm or continue a phase, '
            'and never claim a chat reply approved it: after submitting a phase result, end the turn with a short summary and point to «Tocca a te» in the project card. '
            'Use ask_clarification only for a decisive choice about the result that no phase answers; never to ask how to continue between phases. '
            'Keep checks proportionate: one independent review (purpose=review) per phase that asks for approval, one more only after a correction; '
            'phases without approval need no separate review and reviews are never reviewed. harness_validate is the final policy validation of the finished product '
            'and runs only after the last phase is settled. '
            'First produce the actual requested result, not a report about making it. Keep context and lesson bookkeeping off the production path. The recipe skills are references for the coordinator, not mandatory instructions for every role. Select only skills and tools relevant to each assignment and the actual owner goal; a recipe deliverable list is not an expansion of that goal. '
            'The connections in this task (connections) were chosen by the owner: roles that read the source or write the destination must declare them in roles_json connections; '
            'if a phase does not use them, say why in its note. '
            'At the first turn compare the goal with all phases and, in that same turn, propose skipping every phase the goal does not need '
            '(for example a demo with sample data needs no replica, recurring pipeline or package) with harness_journey(propose_skip=true) and a reason; the owner decides all of them at once.')
