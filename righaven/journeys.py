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


def definition(identifier):
    recipe = next((r for r in recipes.recipes() if r['id'] == identifier), None)
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


def start(workspace, identifier, answers, expected_revision=0):
    recipe = definition(identifier)
    clean = _answers(answers)
    if not clean['goal']:
        raise ValueError('Describe the desired outcome')
    with locked(workspace) as folder:
        previous = _load(folder)
        if previous:
            if previous['recipe_id'] != identifier:
                raise ValueError('This task already has a guided workflow')
            if previous['revision'] != expected_revision:
                raise ValueError('Guided project changed; reload before saving')
            if previous['answers'] == clean:
                return view(workspace, previous)
            value = copy.deepcopy(previous)
            value['answers'] = clean
            for stage in value['stages']:
                if stage['status'] != 'pending':
                    stage['status'] = 'stale'
        else:
            if expected_revision != 0:
                raise ValueError('Guided project changed; reload before saving')
            value = {'recipe_id': identifier, 'recipe_version': recipe['workflow']['version'],
                     'definition': copy.deepcopy(recipe['workflow']), 'answers': clean, 'created_at': utcnow(),
                     'revision': 0, 'stages': [{'id': s['id'], 'status': 'pending', 'evidence': [], 'steps': [], 'note': ''}
                                               for s in recipe['workflow']['stages']]}
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
        if any(by_id[d]['status'] != 'approved' for d in spec['depends_on']):
            if stage['status'] != 'pending':
                stage['status'] = 'stale'
        stage['available'] = all(by_id[d]['status'] == 'approved' for d in spec['depends_on'])
    result['complete'] = all(s['status'] == 'approved' for s in result['stages'])
    result['current'] = next((s['id'] for s in result['stages'] if s['status'] != 'approved' and s['available']), None)
    result['connections_optional'] = True
    return result


def record(workspace, stage_id, evidence, steps, note, expected_revision):
    """Coordinator submits existing artifacts for owner approval; cannot approve its own work."""
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
        if not stage or not stage['available']:
            raise ValueError('Approve prerequisite results before this phase')
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
        target.update(status='review' if kept else 'working', evidence=kept, steps=steps, note=note.strip())
        _invalidate(raw, stage_id)
        _save(folder, raw)
    return view(workspace, raw)


def _invalidate(value, identifier):
    affected = {identifier}
    for spec in value['definition']['stages']:
        if set(spec['depends_on']) & affected:
            affected.add(spec['id'])
            stage = next(s for s in value['stages'] if s['id'] == spec['id'])
            if stage['status'] != 'pending':
                stage['status'] = 'stale'


def decide(workspace, stage_id, approve, expected_revision, note=''):
    if type(approve) is not bool or not isinstance(note, str) or len(note) > 1500 or redact_memory(note) != note:
        raise ValueError('Invalid decision')
    with locked(workspace) as folder:
        raw = _load(folder)
        if not raw or raw['revision'] != expected_revision:
            raise ValueError('Guided project changed; reload before deciding')
        current = view(workspace, raw)
        stage = next((s for s in current['stages'] if s['id'] == stage_id), None)
        if not stage or stage['status'] not in ('review', 'approved') or not stage['available']:
            raise ValueError('This result is not available for approval')
        target = next(s for s in raw['stages'] if s['id'] == stage_id)
        target.update(status='approved' if approve else 'blocked', decision_at=utcnow(), decision_note=note)
        _invalidate(raw, stage_id)
        _save(folder, raw)
    return view(workspace, raw)


def attach_policy(workspace, plan):
    """Pin shipped recipe policy only on an opted-in project, without changing the organization book."""
    journey = view(workspace)
    return pin_policy(plan, journey) if journey else plan


def pin_policy(plan, journey):
    policy = journey['definition']['policy']
    from .policy_book import validate_sheet, revision
    sheet = validate_sheet(policy)
    sheet.update(revision=revision(sheet), reason='Selected guided workflow', steps=[])
    plan = copy.deepcopy(plan)
    plan['sheets'] = [s for s in plan['sheets'] if s['id'] != sheet['id']] + [sheet]
    plan['hash'] = fingerprint({'sheets': plan['sheets']})
    return plan


def instructions(workspace):
    value = view(workspace)
    if not value:
        return ''
    return ('\nGuided project (persisted owner choices): ' + json.dumps(value, ensure_ascii=False) +
            '\nRead the attachments first. Ask at most three decisive unknowns, with recommendations. '
            'Connections are optional; complete a synthetic local path without real accounts. '
            'Compose dynamic roles and use authorized skills/environments for the current outcome. '
            'Record actual evidence and native step IDs with harness_journey; only the owner approves gates. '
            'A DuckDB simulation is not a faithful source-engine replica. Deliver actual BI reports, not just BI tables. '
            'The package must run outside RigHaven and pass its own clean-start, second-run and restart tests. '
            'Never declare production tested without an authorized target verification. '\
            'Do not ask the user to write SQL, JSON, YAML or CLI commands.')
