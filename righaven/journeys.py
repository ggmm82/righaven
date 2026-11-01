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
    return json.loads(path.read_text())


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


def start(workspace, identifier, answers, expected_revision=0, recipe=None, connections=None, owner=None):
    """Save the owner's choices; connections picked in the intake are assigned to the task when its project starts."""
    recipe = recipe or definition(identifier)
    clean = _answers(answers)
    if connections is not None and (not isinstance(connections, list) or len(connections) > 10 or not owner
                                    or not all(isinstance(c, str) for c in connections)):
        raise ValueError('Invalid connections')
    if not clean['goal']:
        raise ValueError('Describe the desired outcome')
    with locked(workspace) as folder:
        previous = _load(folder)
        if previous:
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
            value = {'recipe_id': identifier, 'recipe_version': recipe['workflow']['version'],
                     'recipe': {'title': recipe['it']['title'], 'skills': recipes.skills_of(recipe), 'environment': recipe.get('environment'),
                                'tools': list(recipe['tools']), 'custom': bool(recipe.get('owner')),
                                'outputs': {'it': list(recipe['it']['outputs']), 'en': list(recipe['en']['outputs'])}},
                     'definition': copy.deepcopy(recipe['workflow']), 'answers': clean, 'created_at': utcnow(),
                     'revision': 0, 'stages': [{'id': s['id'], 'status': 'pending', 'evidence': [], 'steps': [], 'note': ''}
                                               for s in recipe['workflow']['stages']]}
        if connections is not None:
            value['connections'] = {'owner': str(owner), 'ids': list(dict.fromkeys(connections))}
        _save(folder, value)
    return view(workspace, value)


def _save(folder, value):
    value['revision'] += 1
    value['updated_at'] = utcnow()
    state.atomic_json(folder / 'journey.json', value)


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


def compact(value):
    """What the coordinator needs each turn: choices, phase states and evidence paths, without the full definition and policy."""
    if not value:
        return None
    recipe = {k: v for k, v in (value.get('recipe') or {}).items() if k != 'outputs'}
    return {'recipe_id': value['recipe_id'], **({'recipe': recipe} if recipe else {}),
            'revision': value['revision'], 'answers': value['answers'], 'current': value['current'],
            'complete': value['complete'], 'awaiting_owner': value.get('awaiting_owner', []),
            'connections': (value.get('connections') or {}).get('ids', []),
            'stages': [{'id': s['id'], 'title': s['title']['it'], 'outcome': s['outcome']['it'], 'status': s['status'], 'available': s['available'],
                        'gate': s.get('gate', True), 'note': s.get('note', '')[:400], 'evidence': [e['path'] for e in s.get('evidence', [])],
                        **({'proposal': s['proposal']} if s.get('proposal') else {}), **({'decision_note': s['decision_note'][:400]} if s.get('decision_note') else {})}
                       for s in value['stages']]}


def instructions(workspace):
    value = view(workspace)
    if not value:
        return ''
    return ('\nGuided project (persisted owner choices): ' + json.dumps(compact(value), ensure_ascii=False) +
            '\nRead the attachments first. Ask at most three decisive unknowns, with recommendations. '
            'Connections are optional; complete a synthetic local path without real accounts. '
            'Compose dynamic roles and use authorized skills/environments for the current outcome. '
            'Record actual evidence and native step IDs with harness_journey; only the owner approves gates, '
            'phases with gate=false complete when their evidence is recorded. '
            + (value['definition'].get('guidance') or '') + (' ' if value['definition'].get('guidance') else '') +
            'Do not ask the user to write SQL, JSON, YAML or CLI commands. '
            'The owner\'s goal (answers.goal) is the final result: keep every phase in service of it and say in one sentence how the current phase moves toward it. '
            'Only the owner approves, asks for corrections or skips a phase, with the buttons in the project card above the chat '
            '(«Approva fase», «Chiedi correzioni», «Salta fase»). Never use ask_clarification or a chat question to approve, confirm or continue a phase, '
            'and never claim a chat reply approved it: after submitting a phase result, end the turn with a short summary and point to «Tocca a te» in the project card. '
            'Use ask_clarification only for a decisive choice about the result that no phase answers. '
            'At the first turn compare the goal with all phases and, in that same turn, propose skipping every phase the goal does not need '
            '(for example a demo with sample data needs no replica, recurring pipeline or package) with harness_journey(propose_skip=true) and a reason; the owner decides all of them at once.')
