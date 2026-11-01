"""Adaptive production workspace: activities, usable versions and recoverable work.

This records operational decisions and file handoffs, never model reasoning.
The worker remains disposable; retries use saved files in a new output folder.
"""
import json
from pathlib import Path
import uuid

from .progress import clean_summary, utcnow, workspace_key
from .work_results import failure_info
from .state import applications, atomic_json
from .source_packages import digest
from .handoff import product_files
from .acceptance import fingerprint
from .project_skills import compact_acceptance, read_document, scoped_file, validate_roles, compile_role, ROLE_ID, redact_memory
from .project_brief import validate_outcome, briefing_issue, orientation
from .strategy import validate as validate_strategy, recovery as method_recovery
from . import policy_workflow, project_store
# Re-exported: callers and tests use projects.<name> for these.
from .project_store import (STEP_ID, PROJECT_ID, MAX_HISTORY, GATEWAY_SESSION, locked, load, workspace_path,  # noqa: F401
                            artifact_path, public_artifact, available_paths)
from .delivery_gate import (media_accepted, delivery_integrity, standard_reviews, standard_review,  # noqa: F401
                            delivery_summary, visible_attempts, review_matches)
from .brief import sync_acceptance, set_user_direction, _direction_result, set_user_control, assert_user_allows_work  # noqa: F401


def read_project(workspace):
    """Compact operational memory: histories remain on disk, not in every LLM turn."""
    if not (Path(workspace) / '.righaven-project').exists():
        return None
    with locked(workspace) as folder:
        value = load(folder, workspace)
    if not value:
        return None
    result = {k: clean_summary(value.get(k, '')) for k in (
        'id', 'brief', 'summary', 'next_action', 'status', 'updated_at', 'product_path')}
    result['project_type'] = value.get('project_type', 'custom')
    result['acceptance'] = compact_acceptance(value.get('acceptance'))
    result['roles'] = value.get('roles', [])
    if value.get('designs'):result['designs'] = value['designs']
    result['memory'] = value.get('memory')
    result['outcome'] = value.get('outcome')
    from .journeys import view
    result['journey'] = view(workspace)
    result['user_direction'] = value.get('user_direction')
    result['user_control'] = value.get('user_control')
    if value.get('connections'):
        from .connections import assigned
        result['connections'] = assigned(workspace, value)
    from .revision import correction_focus
    focus = correction_focus(value)
    if focus:
        result['correction_focus'] = focus
    result['strategy'] = value.get('strategy')
    result['method_recovery'] = value.get('method_recovery')
    result['orientation'] = orientation(value)
    result['brief'] = clean_summary(value.get('brief', ''), 4000)
    result['requirements'] = {k: v for k, v in value.get('requirements', {}).items()
                              if k in ('audio', 'video') and type(v) is bool}
    result['product_path'] = public_artifact(workspace, value.get('product_path', '')) or ''
    result['steps'], result['results'], result['deliveries'], candidates = [], [], [], []
    delivery_inputs, delivery_folders = {}, {}
    for step in value['steps']:
        attempts = step['attempts']
        last = attempts[-1] if attempts else {}
        role_id = step.get('role_id') or last.get('role_id', '')
        role_title = next((r['title'] for r in value.get('roles', []) if r['id'] == role_id), '')
        result['steps'].append({'id': step['id'], 'agent': step['agent'], 'goal': clean_summary(step['goal']),
            'status': step['status'], 'attempt_count': step.get('attempt_count', len(attempts)),
            'role_id': role_id, 'role_title': role_title or last.get('role_title', ''),
            'note': clean_summary(step.get('note', '')), 'error': clean_summary(last.get('error', ''))})
        if step.get('kind'):
            result['steps'][-1]['kind'] = step['kind']
        # Retain previous usable versions when a newer revision failed or hit quota.
        for attempt in visible_attempts(step, value.get('product_path', '')):
            record = attempt.get('delivery_record') or {}
            did = record.get('id') or Path(attempt.get('output_dir', '')).name or step['id']
            metadata = {f.get('path'): f for f in record.get('files', [])}
            inputs = attempt.get('input_files', [])
            if not metadata and workspace:
                # Older deliveries remain grouped, with no retroactive claim of
                # verification. Read metadata only from the scoped job folder.
                directory = workspace_path(workspace, attempt.get('output_dir', ''))
                manifest = artifact_path(workspace, directory / 'handoff.json') if directory else None
                if manifest and manifest.stat().st_size < 100000:
                    try:
                        old = json.loads(manifest.read_text())
                        metadata = {f.get('path'): f for f in old.get('delivery', {}).get('files', []) if isinstance(f, dict)}
                        inputs = old.get('source_files', [])
                    except (OSError, ValueError, AttributeError):
                        pass
            delivery_inputs[did] = [p for p in (workspace_path(workspace, f) for f in inputs) if p]
            delivery_folders[did] = workspace_path(workspace, attempt.get('output_dir', ''))
            result['deliveries'].append({'id': did, 'title': clean_summary(record.get('title') or step['goal']),
                'agent': step['agent'], 'at': attempt.get('finished_at', ''),
                'technical_status': record.get('technical_status', 'not_verified'),
                'issues': [clean_summary(s) for s in record.get('issues', [])[:5]],
                'current': value.get('product_path') in attempt.get('output_files', []),
                'purpose': attempt.get('context', {}).get('purpose', 'work')})
            if record.get('finalization_pending'):
                result['deliveries'][-1]['finalization_pending'] = [clean_summary(s) for s in record['finalization_pending'][:5]]
            coverage=record.get('source_coverage')
            if coverage:
                result['deliveries'][-1]['source_coverage']=coverage
            if record.get('timing'):
                result['deliveries'][-1]['timing']=record['timing']
            if record.get('reused_archive_checks'):
                result['deliveries'][-1]['reused_archive_checks']=record['reused_archive_checks']
            for filename in (available_paths(workspace, attempt) + attempt.get('previews', []))[:40]:
                meta = metadata.get(filename, {})
                candidates.append({'path': filename, 'agent': step['agent'], 'activity': step['id'],
                        'delivery_id': did, 'role': clean_summary(meta.get('role', 'preview' if filename in attempt.get('previews', []) else 'file')),
                        'open_with': clean_summary(meta.get('open_with', '')),
                        'limitations': [clean_summary(s) for s in meta.get('limitations', [])[:3]],
                        'editability': clean_summary(meta.get('editability', '')),
                        'label': clean_summary(Path(filename).name), 'validated': attempt.get('validated',
                        attempt.get('status') == 'completed'), 'at': attempt.get('finished_at', '')})
    current_ids = {d['id'] for d in result['deliveries'] if d['current']}
    candidates.sort(key=lambda r: (r['delivery_id'] in current_ids, r['path'] == value.get('product_path'), r['at']), reverse=True)
    seen = set()
    for record in candidates:
        path = public_artifact(workspace, record['path'])
        if path and path not in seen:
            seen.add(path)
            result['results'].append({**record, 'path': path})
        if len(result['results']) >= 160:
            break
    samples = {d['id'] for d in result['deliveries'] if d['purpose'] == 'preview'}
    sample_exports = [r for r in result['results'] if r['delivery_id'] in samples
                      and r['role'] in ('export', 'preview') and r['validated']]
    if sample_exports:
        result['latest_sample'] = max(sample_exports, key=lambda r: (r['at'], r['role'] == 'export'))
    used = {d['id'] for d in result['deliveries'] if d['current']}
    pending = list(used)
    while pending:
        did = pending.pop()
        for parent, directory in delivery_folders.items():
            if parent not in used and directory and any(p.is_relative_to(directory) for p in delivery_inputs.get(did, [])):
                used.add(parent)
                pending.append(parent)
    from .revisions import annotate
    annotate(result['deliveries'], value, workspace, artifact_path)
    versions = [d for d in result['deliveries'] if d.get('version_state')]
    if versions:
        result['version_selection'] = {state: next((d['id'] for d in sorted(versions,
            key=lambda d: d['at'], reverse=True) if d.get('version_state') == state), None)
            for state in ('approved', 'candidate', 'partial')}
    for delivery in result['deliveries']:
        delivery['contribution'] = delivery['id'] in used and not delivery['current']
    result['deliveries'].sort(key=lambda d: (d['current'], d['contribution'], d['at']), reverse=True)
    result['deliveries'] = result['deliveries'][:30]
    result['quality_status'] = 'not_reviewed'
    for attempt in standard_reviews(value):
        review = attempt['quality_review']
        if review_matches(value, review, result['product_path'], workspace):
            matches = not value.get('acceptance') or review.get('contract_hash') == value['acceptance']['hash']
            result['quality_status'] = review['status'] if matches else 'needs_review'
            result['review_criteria'] = review.get('criteria', []) if matches else []
            result['review_checkpoint'] = review.get('checkpoint') if matches else None
            result['review_unavailable_methods'] = review.get('unavailable_methods', []) if matches else []
            result['review_observation_limits'] = review.get('observation_limits', []) if matches else []
            result['revision_actions'] = review.get('revision_actions', []) if matches else []
            if matches and review.get('findings'):
                result['review_findings'] = review['findings']
            result['comparison'] = review.get('comparison') if matches else None
            break
    accepted = value.get('user_acceptance') or {}
    if accepted.get('product_path') == value.get('product_path') and accepted.get('status') == 'passed':
        result['quality_status'] = 'accepted_by_user'
    result['governance'] = policy_workflow.view(workspace, value)
    if (value.get('checkpoint') or {}).get('status') == 'awaiting_user':
        result['checkpoint'] = {k: value['checkpoint'][k] for k in ('status', 'steps', 'at')}
    attention = value.get('attention')
    result['attention'] = {k: clean_summary(attention.get(k)) for k in ('code', 'message', 'action')} if isinstance(attention, dict) else None
    if not result['attention'] and value.get('schema_version') != 2:
        # Existing projects migrate without erasing recoverable output or demanding a new plan.
        failed = [s for s in value['steps'] if s['status'] in ('needs_revision', 'paused') and s['attempts']]
        if failed:
            latest = max(failed, key=lambda s: s['attempts'][-1].get('finished_at', ''))
            error = latest['attempts'][-1].get('error')
            if error:
                result['attention'] = failure_info(error)
    if not result['status']:
        result['status'] = 'working' if any(s['status'] == 'running' for s in value['steps']) else 'review'
    if result['status'] == 'blocked' and not value.get('strategy'):
        recovery = method_recovery(workspace, value)
        if recovery:
            result.update(method_recovery=recovery, status='review', summary=recovery['message'],
                          next_action='Rivalutare il metodo e le scelte provvisorie della squadra.')
    return result


def _plan_input(project_type, steps, status, outcome, requirements):
    """Validated outcome and activities of a plan update, before the project is locked."""
    if project_type not in ('', 'custom', 'animated_video'):
        raise ValueError('Tipo di progetto non valido')
    if not isinstance(steps, list) or len(steps) > 64:
        raise ValueError('Usa al massimo 64 attività')
    if status not in ('', 'working', 'review', 'ready', 'blocked', 'idle', 'clarifying'):
        raise ValueError('Stato progetto non valido')
    outcome = validate_outcome(outcome) if outcome is not None else None
    if requirements is not None and (not isinstance(requirements, dict) or any(
            k not in ('audio', 'video') or type(v) is not bool for k, v in requirements.items())):
        raise ValueError('I requisiti media accettano audio e video come booleani')
    known, incoming = {a['id'] for a in applications()} | {'workspace'}, []
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError('Attività non valida')
        sid, agent, goal = step.get('id', ''), step.get('agent'), step.get('goal', '')
        if not isinstance(sid, str) or not STEP_ID.fullmatch(sid) or sid in {s['id'] for s in incoming}:
            raise ValueError('ID attività non valido o duplicato')
        if agent not in known or not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise ValueError('Ogni attività richiede uno specialista del catalogo e un obiettivo concreto')
        if 'role_id' in step and (not isinstance(step['role_id'], str) or not ROLE_ID.fullmatch(step['role_id'])):
            raise ValueError('ID ruolo non valido')
        deps = step.get('depends_on', [])
        if not isinstance(deps, list) or any(not isinstance(d, str) or not STEP_ID.fullmatch(d) for d in deps):
            raise ValueError('Riferimenti degli input non validi')
        if step.get('status', 'pending') not in ('pending', 'skipped', 'review','completed'):
            raise ValueError('Le attività aggiornabili possono essere pending, skipped o review; completed può soltanto confermare un esito già registrato.')
        incoming.append({**step, 'depends_on': deps})
    return outcome, incoming


def _apply_outcome(value, outcome, source_turn):
    """Record the intended result; tool choices and answers must come from a real user turn."""
    question_turn = value.get('brief_question_turn')
    if (value.get('outcome') or {}).get('questions') and not outcome.get('questions') and question_turn:
        if not source_turn or source_turn == question_turn:
            raise ValueError('Le domande sul risultato attendono una nuova risposta reale dell’utente; non cancellarle nello stesso turno.')
    presented = value.setdefault('tool_options_turn', {})
    previous_choices = {d['id']: d.get('chosen', '') for d in (value.get('outcome') or {}).get('tool_options', [])}
    for decision in outcome.get('tool_options', []):
        if not decision['chosen']:
            presented[decision['id']] = source_turn or presented.get(decision['id'], '')
        elif previous_choices.get(decision['id']) != decision['chosen'] and (
                not source_turn or decision['id'] not in presented or presented[decision['id']] == source_turn):
            raise ValueError('La scelta tra le alternative «' + decision['decision'] + '» spetta all’utente: '
                             'presentale prima con pregi, difetti e consiglio, poi registra chosen dopo la sua risposta.')
    if outcome.get('questions') and source_turn:
        value['brief_question_turn'] = source_turn
    elif not outcome.get('questions'):
        value.pop('brief_question_turn', None)
    if value.get('outcome') != outcome:
        value.pop('user_acceptance', None)
        if value.get('status') == 'ready':
            value['status'] = 'review'
    value['outcome'] = outcome
    if not briefing_issue(outcome) and value.get('status') == 'clarifying':
        value['status'] = 'working'


def _merge_steps(value, incoming):
    """Add or update activities; completed may only confirm a recorded, unchanged attempt."""
    for item in incoming:
        previous = next((s for s in value['steps'] if s['id'] == item['id']), None)
        if item.get('status')=='completed':
            if (not previous or previous['status']!='completed' or not previous['attempts']
                    or any(item.get(k)!=previous.get(k) for k in ('agent','goal','depends_on'))
                    or 'role_id' in item and item['role_id']!=previous.get('role_id')):
                raise ValueError('completed richiede un incarico già concluso e invariato: il piano non può dichiarare un’esecuzione mai avvenuta.')
            continue
        if previous:
            if previous['status'] == 'running':
                raise ValueError('Non modificare un’attività in esecuzione')
            previous.update(agent=item['agent'], goal=item['goal'], depends_on=item['depends_on'])
            if 'role_id' in item:
                previous['role_id'] = item['role_id']
            if 'status' in item:
                previous['status'] = item['status']
        else:
            value['steps'].append({**item, 'status': item.get('status', 'pending'), 'attempts': []})
    if len(value['steps']) > 64:
        raise ValueError('Il progetto ha raggiunto 64 attività; archivia quelle concluse prima di un nuovo progetto')


def _set_product(workspace, value, product_path, status):
    """The shown product must be a file actually produced and verified in this project."""
    path = artifact_path(workspace, product_path)
    draft = status == 'review'
    produced = [p for s in value['steps'] for a in s['attempts']
                if a.get('validated', a.get('status') == 'completed') for p in a.get('output_files', [])]
    reviewed_draft = path and draft and any(
        a.get('validated') and artifact_path(workspace, (a.get('quality_review') or {}).get('product_path', '')) == path
        and (a.get('quality_review') or {}).get('sha256') == digest(path)
        and (a.get('quality_review') or {}).get('contract_hash') == (value.get('acceptance') or {}).get('hash')
        for s in value['steps'] for a in s['attempts'])
    if not path or not (any(artifact_path(workspace, p) == path for p in produced) or reviewed_draft):
        raise ValueError('Il prodotto deve essere un file realmente prodotto e verificato da uno specialista')
    if not draft and value.get('requirements') and not any(product_path in a.get('verified_products', [])
            for s in value['steps'] for a in s['attempts']):
        raise ValueError('Prima della consegna finale usa harness_delegate con purpose=delivery per controllare il file completo')
    if value.get('product_path') != product_path:
        value.pop('policy_validation', None)
    value['product_path'] = product_path


def _check_ready(workspace, value, require_settled):
    """Completion gate: brief answered, delivery integrity, separate review and Policy Plan validation."""
    from .journeys import _load as load_journey, view as journey_view
    journey = load_journey(Path(workspace).resolve() / '.righaven-project')
    if journey and not journey_view(workspace, journey)['complete']:
        raise ValueError('Complete the guided phases and obtain owner approval before final delivery')
    if require_settled and (not (value.get('acceptance') or {}).get('user_requests') or any(
            step['status'] in ('pending','running','paused','needs_revision') for step in value['steps'])):
        raise ValueError('Completamento automatico sospeso: richiesta o attività ancora da verificare')
    if value.get('outcome') and briefing_issue(value['outcome']):
        raise ValueError('Rispondi prima alle domande sul risultato atteso')
    acceptance = value.get('acceptance') or {}
    if acceptance.get('request_manifest'):
        for document in json.loads(read_document(workspace, acceptance['request_manifest'])):
            read_document(workspace, document)
    target = artifact_path(workspace, value.get('product_path', ''))
    integrity = delivery_integrity(workspace, value, target)
    if integrity:
        raise ValueError(integrity)
    target_hash = digest(target)
    accepted = value.get('user_acceptance') or {}
    owner_accepted = accepted.get('product_path') == value.get('product_path') and accepted.get('sha256') == target_hash
    if not owner_accepted and (standard_review(workspace, value, target_hash) or {}).get('status') != 'passed':
        raise ValueError('Manca una revisione separata valida del prodotto rispetto alla richiesta corrente: usa purpose=review e quality-review.json, coprendo requisiti e riferimenti. Se il metodo richiesto non è disponibile mantieni status=review; non rigenerare né fingere la verifica.')
    if policy_workflow.governed(value) and not owner_accepted:
        report = policy_workflow.validation(workspace, value)
        if report['status'] != 'passed':
            pending = [s['id'] + ': ' + s['status'] for s in report['sheets'] if s['status'] != 'passed']
            raise ValueError('La validazione finale del Policy Plan non è superata (' + ', '.join(pending) +
                             '). Usa harness_validate sul prodotto finito e correggi le violazioni prima della consegna.')
        value['policy_validation'] = {**report, 'at': utcnow()}


def _apply_status(workspace, value, status):
    """Set the visible status; a blocked project first looks for a method recovery."""
    value['status'] = status
    if status == 'ready':
        value['attention'] = None
        policy_workflow.close_at_delivery(value)
    if status == 'blocked':
        recovery = method_recovery(workspace, value)
        if recovery:
            value.update(status='review', method_recovery=recovery, summary=recovery['message'],
                next_action='Rivalutare le scelte della squadra e il metodo; il risultato richiesto resta da completare.')
        else:
            value.pop('method_recovery', None)
            if (value.get('strategy') or {}).get('state') == 'needs_user':
                value['next_action'] = value['strategy']['user_action']
    elif status in ('working', 'ready', 'idle'):
        value.pop('method_recovery', None)


def create_plan(workspace, brief, steps, project_type='', omissions=None, *, summary='', next_action='',
                status='', product_path='', requirements=None, outcome=None, strategy=None, source_turn='', require_settled=False):
    """Update an evolving brief and activity board, preserving work and versions."""
    outcome, incoming = _plan_input(project_type, steps, status, outcome, requirements)
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            if not brief.strip():
                raise ValueError('Specifica il risultato richiesto')
            value = {'id': uuid.uuid4().hex, 'workspace_key': workspace_key(workspace),
                'brief': clean_summary(brief, 4000), 'project_type': project_type or 'custom',
                'created_at': utcnow(), 'steps': [], 'requirements': {},
                'governance': dict(policy_workflow.GOVERNANCE)}
        if brief:
            value['brief'] = clean_summary(brief, 4000)
        if outcome is not None:
            _apply_outcome(value, outcome, source_turn)
        if project_type:
            value['project_type'] = project_type
        if value['project_type'] == 'animated_video' and not value.get('requirements'):
            value['requirements'] = {'video': True, 'audio': not bool((omissions or {}).get('soundcraft'))}
        if requirements is not None:
            value['requirements'] = requirements
        _merge_steps(value, incoming)
        for key, text in [('summary', summary), ('next_action', next_action)]:
            if text:
                value[key] = clean_summary(text)
        if product_path:
            _set_product(workspace, value, product_path, status)
        if strategy is not None:
            value['strategy'] = validate_strategy(workspace, strategy, applications(), (value.get('acceptance') or {}).get('hash'))
            value.pop('method_recovery', None)
            if value.get('status') == 'blocked' and value['strategy']['state'] != 'needs_user':
                value['status'] = 'review'
        from .journeys import _load as load_journey, pin_policy
        journey = load_journey(folder)
        if journey and value.get('policy_plan'):
            # A recipe namespace may collide with a later administrator policy: let core resolve organization sheets first.
            value['policy_plan']['sheets']=[s for s in value['policy_plan']['sheets'] if s.get('source_recipe')!=journey['recipe_id']]
        changed = policy_workflow.ensure_plan(value) if policy_workflow.governed(value) else None
        if journey:
            value['policy_plan'] = pin_policy(value['policy_plan'], journey)
            value.setdefault('checkpoints', {'enabled': False, 'source': 'guided_phase_gates'})
        if status == 'ready':
            _check_ready(workspace, value, require_settled)
        if status:
            _apply_status(workspace, value, status)
        if value.get('outcome') and briefing_issue(value['outcome']):
            value['status'] = 'clarifying'
        value.update(schema_version=2, updated_at=utcnow())
        atomic_json(folder / 'project.json', value)
    if changed:
        record_policy_event(workspace, value, changed)
    return read_project(workspace)


def record_policy_event(workspace, value, operation, status='completed', detail=''):
    from .audit_log import append
    plan = value.get('policy_plan') or {}
    append(workspace, 'Policy Book', operation, status,
           detail=detail or 'Sheet: ' + ', '.join(s['id'] for s in plan.get('sheets', [])), correlation=plan.get('hash', ''))


def set_policy_plan(workspace, selections):
    """Coordinator decision on the optional sheets; mandatory sheets are added by the runtime."""
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            raise ValueError('Definisci prima il brief e l’Execution Plan')
        if not policy_workflow.governed(value):
            raise ValueError('Questo progetto è precedente al Policy Book: prosegui con le verifiche esistenti')
        from .journeys import _load as load_journey, pin_policy
        journey = load_journey(folder)
        if journey and isinstance(selections,list):
            automatic={s['id'] for s in (value.get('policy_plan') or {}).get('sheets',[]) if s.get('source_recipe')==journey['recipe_id']}
            selections=[s for s in selections if not isinstance(s,dict) or s.get('id') not in automatic]
        plan = policy_workflow.policy_book.build_plan(selections, [s for s in value['steps'] if s.get('kind') != 'validation'])
        if journey:
            plan = pin_policy(plan, journey)
        if plan['hash'] == (value.get('policy_plan') or {}).get('hash') and value['policy_plan']['selected_by'] == 'coordinator':
            return
        value['policy_plan'] = plan
        value.pop('policy_validation', None)
        value['updated_at'] = utcnow()
        atomic_json(folder / 'project.json', value)
    record_policy_event(workspace, value, 'Policy Plan definito dal coordinatore')


def set_checkpoints(workspace, enabled):
    """Owner choice: pause after every phase to discuss results (default) or not."""
    if type(enabled) is not bool:
        raise ValueError('Indica se fermarsi a ogni fase')
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value or not policy_workflow.governed(value):
            raise ValueError('Le pause per fase valgono per i progetti governati dal Policy Book')
        value['checkpoints'] = {'enabled': enabled, 'updated_at': utcnow()}
        if not enabled and (value.get('checkpoint') or {}).get('status') == 'awaiting_user':
            value['checkpoint'] = {**value['checkpoint'], 'status': 'waived', 'closed_at': utcnow()}
        value['updated_at'] = utcnow()
        atomic_json(folder / 'project.json', value)
    record_policy_event(workspace, value, 'Pause per fase ' + ('attivate' if enabled else 'disattivate dal proprietario'))
    return value['checkpoints']


def governance_state(workspace):
    """Full project record for the policy engine; histories stay out of LLM turns."""
    with locked(workspace) as folder:
        return load(folder, workspace)


def save_probe_results(workspace, results):
    """Record executable probe outcomes, keyed by sheet/check and bound to the product hash."""
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            raise ValueError('Progetto non disponibile')
        value['policy_probes'] = {**value.get('policy_probes', {}), **results}
        value['updated_at'] = utcnow()
        atomic_json(folder / 'project.json', value)
    for key, result in results.items():
        record_policy_event(workspace, value, 'Probe ' + key, 'completed' if result['status'] == 'passed' else 'failed',
                            result.get('evidence', ''))


def save_policy_validation(workspace, report):
    """Record the aggregated verdict; the completion gate always recomputes it from files."""
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            raise ValueError('Progetto non disponibile')
        value['policy_validation'] = {**report, 'at': utcnow()}
        if report['status'] == 'passed':
            value.update(summary='Validazione finale superata per tutte le policy sheet.',
                         next_action='Consegna il prodotto validato.')
        elif report['status'] in ('failed', 'blocked'):
            value.update(status='review', summary='Validazione finale non superata: violazioni da correggere.',
                         next_action='Correggi le violazioni aggregate e ripeti harness_validate.')
        value['updated_at'] = utcnow()
        atomic_json(folder / 'project.json', value)
    record_policy_event(workspace, value, 'Validazione finale multi-policy', 'completed' if report['status'] == 'passed' else 'failed',
                        detail='; '.join(s['id'] + ': ' + s['status'] for s in report['sheets']) or report['integrity']['issue'])
    return value['policy_validation']


def reconcile_completion(workspace):
    """Publish only through the same hash/contract/source gates as explicit completion."""
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value or value.get('status') in ('ready','clarifying') or not value.get('product_path'):
            return False
        if any(step['status'] in ('pending','running','paused','needs_revision') for step in value['steps']):
            return False
    try:
        create_plan(workspace, '', [], status='ready', require_settled=True,
            summary='Risultato verificato e consegnato.', next_action='Apri il risultato o richiedi una revisione.')
    except ValueError:
        return False
    return True


def mark_incomplete_turn(workspace):
    """Never leave an exhausted completion guard looking like task success."""
    if reconcile_completion(workspace):
        return
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value or value.get('status') == 'ready':
            return
        value.update(status='review', attention={'code': 'incomplete_objective',
            'message': 'Il coordinatore ha chiuso senza completare il risultato richiesto.',
            'action': 'I file sono conservati. Riprendi dal prossimo obiettivo oppure modifica metodo o modello della squadra.'},
            updated_at=utcnow())
        atomic_json(folder / 'project.json', value)


def accept_delivery(workspace, delivery_id):
    """Explicit owner UI action; never callable by the coordinator as a tool."""
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value or any(s['status'] == 'running' for s in value['steps']):
            raise ValueError('Attendi la conclusione del lavoro attivo')
        if value.get('outcome') and briefing_issue(value['outcome']):
            raise ValueError('Rispondi prima alle domande sul risultato atteso')
        product = artifact_path(workspace, value.get('product_path', ''))
        records = [a.get('delivery_record') or {} for s in value['steps'] for a in s['attempts']]
        delivery = next((r for r in records if r.get('id') == delivery_id), None)
        if not product or not delivery or delivery.get('technical_status') != 'passed' or not media_accepted(delivery, value) or not any(
                artifact_path(workspace, f.get('path', '')) == product for f in delivery.get('files', [])):
            raise ValueError('Consegna selezionata cambiata o tecnicamente incompleta')
        if not all(artifact_path(workspace, f.get('path', '')) and digest(artifact_path(workspace, f['path'])) == f.get('sha256')
                   for f in delivery.get('files', [])):
            raise ValueError('I file sono cambiati dopo il collaudo: verificare la nuova versione')
        acceptance = {'status': 'passed', 'product_path': value['product_path'],
            'sha256': digest(product), 'contract_hash': (value.get('acceptance') or {}).get('hash'),
            'delivery_id': delivery_id, 'at': utcnow()}
        if policy_workflow.governed(value):
            # The owner may accept despite open policy findings; record what they accepted.
            report = policy_workflow.validation(workspace, value)
            acceptance['policy_validation'] = {'status': report['status'],
                'sheets': {s['id']: s['status'] for s in report['sheets']}}
        value.update(user_acceptance=acceptance,
            status='ready', attention=None, summary='Versione accettata da te; consegna completa disponibile.',
            next_action='Scarica il prodotto e il pacchetto sorgenti della consegna selezionata.', updated_at=utcnow())
        atomic_json(folder / 'project.json', value)
    return read_project(workspace)


def revise_step(workspace, step_id, reason):
    if not reason.strip():
        raise ValueError('Specifica il problema da correggere')
    with locked(workspace) as folder:
        value = load(folder, workspace)
        step = next((s for s in (value or {}).get('steps', []) if s['id'] == step_id), None)
        if not step or step['status'] == 'running':
            raise ValueError('Attività non disponibile per la revisione')
        # A new creative revision is not a lifetime retry and does not invalidate the team.
        step.update(status='pending', revision=clean_summary(reason), revision_id=uuid.uuid4().hex)
        value.update(status='review', next_action=clean_summary(reason), updated_at=utcnow())
        atomic_json(folder / 'project.json', value)
    return read_project(workspace)


def archive_plan(workspace, reason):
    if not reason.strip():
        raise ValueError('Specifica il motivo dell’archiviazione')
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            return None
        if any(s['status'] == 'running' for s in value['steps']):
            raise ValueError('Attendi il termine dell’incarico attivo')
        value.update(archived_at=utcnow(), archive_reason=clean_summary(reason))
        atomic_json(folder / (value['id'] + '.json'), value)
        (folder / 'project.json').unlink()
    return {'id': value['id'], 'archived': True, 'files_preserved': True}


def execute_step(workspace, agent, task, step_id, invoke, *, provider=None, purpose='work', request_id='', role=None, policy_sheet=None):
    if purpose not in ('work', 'preview', 'review', 'integration', 'delivery'):
        raise ValueError('Scopo incarico non valido')
    if not read_project(workspace):
        create_plan(workspace, clean_summary(task), [])
    with locked(workspace) as folder:
        value = load(folder, workspace)
        assert_user_allows_work(value)
        if value.get('outcome') and briefing_issue(value['outcome']):
            raise ValueError('Prima della produzione completa le scelte sul risultato: ' + briefing_issue(value['outcome']))
        if purpose != 'review':
            from .journeys import _load as load_journey, view as journey_view
            saved_journey = load_journey(folder)
            if saved_journey:
                guided = journey_view(workspace, saved_journey)
                current = next((s for s in guided['stages'] if s['id'] == guided['current']), None)
                if not current or current['status'] != 'working' or step_id not in current['steps']:
                    raise ValueError('Start the current guided phase with harness_journey and its native activity IDs; wait for owner approval before later phases')
            policy_workflow.require_production(value)
            discussed = policy_workflow.pass_checkpoint(value, request_id)
        if policy_sheet is not None and (purpose != 'review' or not policy_workflow.governed(value) or policy_sheet['id'] not in
                {s['id'] for s in (value.get('policy_plan') or {}).get('sheets', [])}):
            raise ValueError('La validazione di una policy sheet richiede una revisione prevista dal Policy Plan')
        step = next((s for s in value['steps'] if s['id'] == step_id), None) if step_id else None
        if not step:
            sid = step_id or agent + '-' + uuid.uuid4().hex[:8]
            if not STEP_ID.fullmatch(sid) or agent not in ({a['id'] for a in applications()} | {'workspace'}) or len(value['steps']) >= 64:
                raise ValueError('Attività o specialista non valido')
            label = (role or {}).get('title') or {'review': 'Verifica del risultato', 'preview': 'Preparazione di un campione',
                'integration': 'Integrazione dei contributi', 'delivery': 'Preparazione della consegna'}.get(purpose)
            if policy_sheet is not None:
                label = 'Validazione policy: ' + policy_sheet['title']
            step = {'id': sid, 'agent': agent, 'goal': clean_summary(label or task), 'depends_on': [], 'attempts': [], 'status': 'pending'}
            if policy_sheet is not None:
                step['kind'] = 'validation'
            value['steps'].append(step)
        if step['status'] == 'running':
            raise ValueError('Questa attività è già in esecuzione')
        latest = step['attempts'][-1] if step['attempts'] else {}
        if (request_id and step['status'] == 'completed' and latest.get('context', {}).get('request') == request_id
                and latest.get('context', {}).get('purpose') == purpose and latest.get('task') == clean_summary(task, 1500)):
            # The same assignment in the same user turn: return what is recorded instead of running it again.
            return json.dumps({'ok': True, 'duplicate': True, 'activity': {'id': step['id'], 'status': step['status']},
                               'output_dir': latest.get('output_dir', ''), 'available_files': latest.get('output_files', [])[:40],
                               'instruction': 'Incarico identico già concluso in questo turno: usa il risultato registrato, non rilanciarlo.'},
                              ensure_ascii=False)
        step.update(agent=agent, purpose=purpose)
        if role:
            step['role_id'] = role['id']
        previous = step['attempts'][-1] if step['attempts'] else {}
        context = {'provider': provider, 'revision': step.get('revision_id', ''), 'purpose': purpose, 'request': request_id,
                   'contract':(value.get('acceptance') or {}).get('hash'), 'role': role.get('version') if role else None}
        if policy_sheet is not None:
            context['policy'] = {'sheet': policy_sheet['id'], 'revision': policy_sheet['revision']}
        previews = [a for a in step['attempts'] if a.get('context',{}).get('purpose') == 'preview'
                    and a.get('context',{}).get('revision','') == context['revision']
                    and (not a.get('context',{}).get('contract') or a['context']['contract'] == context['contract'])]
        if purpose == 'preview' and len(previews) >= 2 and all(a.get('status') == 'needs_revision' for a in previews[-2:]):
            return json.dumps({'ok':False,'retry_blocked':True,'checkpoint_reassessment':True,
                'error':'Due prove insufficienti sullo stesso checkpoint: rivaluta il contributo all’obiettivo prima di un altro ritocco.',
                'goal':(value.get('outcome') or {}).get('result') or value['brief'],
                'instruction':'Conserva i risultati e distingui requisito richiesto da dettaglio scelto dalla squadra. '
                    'Puoi integrare/consegnare le parti valide o cambiare campione/metodo senza abbassare i requisiti dell’utente. '
                    'Per riprovare questo checkpoint usa harness_plan(revise_step_id) con la decisione concreta: '
                    'beneficio atteso sul prodotto finale, causa verificata e cosa cambia nella prova. Non chiedere procedi per il lavoro già autorizzato.',
                'available_results':read_results(value,workspace)},ensure_ascii=False)
        if previous.get('context') == context and previous.get('error'):
            failure = failure_info(previous['error'])
            if not failure['retryable']:
                return json.dumps({'ok': False, 'attention': failure, 'available_results': read_results(value, workspace),
                    'error': failure['message'], 'retry_blocked': True}, ensure_ascii=False)
            recent = step['attempts'][-2:]
            if len(recent) == 2 and all(a.get('context') == context and a.get('error') == previous['error']
                    and not a.get('output_files') for a in recent):
                return json.dumps({'ok': False, 'error': 'Due tentativi identici senza risultati: cambia approccio, '
                    'riduci l’incarico o integra i file recuperati. Le altre attività restano disponibili.',
                    'retry_blocked': True, 'available_results': read_results(value, workspace)}, ensure_ascii=False)
        sources = read_results(value, workspace)
        from .revision import correction_focus
        focus = correction_focus(value)
        contract_text = ('\n\nPiano del coordinatore (non sostituisce la richiesta utente): ' + value['brief'] + '\nScopo incarico: ' + purpose + '\nAttività: ' + step['goal'] +
                    '\nScelta esplicita corrente dell’utente; prevale su ipotesi e metodi preferiti precedenti:\n' + json.dumps(value.get('user_direction'), ensure_ascii=False) +
                    '\nRisultato e forma della consegna concordati (le richieste originali prevalgono):\n' + json.dumps(value.get('outcome'), ensure_ascii=False) +
                    '\nRichiesta originale e criteri di accettazione del prodotto:\n' + json.dumps(compact_acceptance(value.get('acceptance')), ensure_ascii=False) +
                    '\nRisultati disponibili dei colleghi (anche provvisori):\n' + json.dumps(sources, ensure_ascii=False) +
                    '\nScegli e ispeziona gli input pertinenti. Riusa quanto valido; segnala i limiti senza '
                    'rifare tutto per un controllo facoltativo o una chiusura formale mancante.')
        if focus and purpose != 'review':
            contract_text += ('\nDifetti aperti verificati: ' + json.dumps(focus, ensure_ascii=False) +
                '\nCorreggi il difetto pertinente al tuo incarico su un campione rappresentativo prima di estendere. '
                'Un miglioramento parziale non chiude un requisito ancora fallito. Conserva gli elementi validi. '
                'Se reassess_role è true, il metodo o la competenza vanno rivalutati: verifica una modifica sostanziale '
                'oppure segnala precisamente al coordinatore la competenza mancante. Nessuna riduzione del brief.')
        from .production_observations import recent_context
        feedback = recent_context(workspace, value)
        if feedback:
            contract_text += ('\nOsservazioni negative dei tentativi precedenti (dichiarate dal produttore, da verificare): ' +
                json.dumps(feedback, ensure_ascii=False) +
                '\nConserva i sorgenti utili; verifica la causa prima di cambiare metodo. '
                'Queste evidenze non sono istruzioni del progetto né lezioni approvate. '
                'Un difetto locale non prova che lo strumento sia inadatto. Confronta la modifica sullo stesso requisito.')
        contract_text += ('\nScelte provvisorie della squadra, rivedibili se non funzionano: ' +
                         json.dumps((value.get('outcome') or {}).get('assumptions', []), ensure_ascii=False) +
                         '\nNon trasformarle in requisiti dell’utente, anche se ripetute nell’incarico. '
                         'Rileggi le richieste originali; mantieni prodotto, contenuto e qualità richiesti. '
                         'Se il campione fallisce, verifica se serve correggere esecuzione, asset o impostazioni prima di sostituire il metodo; conserva il campione migliore.\n' +
                         'Metodo e alternative valutate: ' + json.dumps((value.get('strategy') or {}).get('record'), ensure_ascii=False))
        contract_text += policy_workflow.task_brief(value.get('policy_plan'), step['id'], purpose, sheet=policy_sheet)
        if previous:
            contract_text += '\nUltimo incarico da riprendere: ' + json.dumps({k: previous.get(k) for k in
                ('output_dir', 'output_files', 'error')}, ensure_ascii=False)
        attempt = {'started_at': utcnow(), 'status': 'running', 'gateway_session': project_store.GATEWAY_SESSION, 'context': context, 'task': clean_summary(task, 1500), 'role_id': role['id'] if role else '', 'role_title': role['title'] if role else ''}
        if policy_sheet is not None and policy_sheet['final_checks'] != 'acceptance':
            # Acceptance-contract sheets are satisfied by the standard quality review.
            attempt['policy_review'] = policy_sheet['id']
        attempt['project_brief'] = clean_summary(value.get('brief',''),4000)
        attempt['project_title'] = clean_summary((value.get('outcome') or {}).get('title') or value.get('brief',''),400)
        installed = {app['id']: app['version'] for app in applications()}
        attempt['tool_environment'] = scoped_file(workspace, 'tool-environments/' + fingerprint(installed) + '.json', json.dumps(installed, sort_keys=True))
        if purpose == 'delivery':
            value['version_counter'] = value.get('version_counter', 0) + 1
            attempt['version_number'] = value['version_counter']
        if role and role.get('scope'):
            attempt['role_scope'] = role['scope']
        history = step['attempts'][-(MAX_HISTORY - 3):]
        last_usable = next((a for a in reversed(step['attempts']) if a.get('status') == 'completed'), None)
        if last_usable and last_usable not in history:
            history.insert(0, last_usable)
        selected = next((a for a in reversed(step['attempts']) if value.get('product_path') in a.get('output_files', [])), None)
        if selected is not None and selected not in history:
            history.insert(0, selected)
        step['attempts'] = [*history, attempt]
        step['attempt_count'] = step.get('attempt_count', len(step['attempts']) - 1) + 1
        step['status'] = 'running'
        value.update(schema_version=2, status='working', attention=None, updated_at=utcnow())
        value.pop('method_recovery', None)
        atomic_json(folder / 'project.json', value)
        project_id, sid = value['id'], step['id']
    if purpose != 'review' and discussed:
        record_policy_event(workspace, value, 'Fase discussa con l’utente', detail=', '.join(discussed['steps']))

    def started(output_dir):
        with locked(workspace) as folder:
            current = load(folder, workspace)
            next(s for s in current['steps'] if s['id'] == sid)['attempts'][-1]['output_dir'] = output_dir
            atomic_json(folder / 'project.json', current)

    try:
        result = json.loads(invoke(task + contract_text, started))
        if not isinstance(result, dict):
            raise ValueError('Risposta dello specialista non valida')
    except Exception as exc:
        result = {'ok': False, 'error': clean_summary(exc)}
    handoff = result.get('handoff') or {}
    notes = [clean_summary(c.get('name')) for c in handoff.get('checks', []) if c.get('status') != 'passed' and c.get('scope') != 'historical']
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if value['id'] != project_id:
            raise RuntimeError('Progetto cambiato durante l’incarico')
        presentation={k:value.get(k) for k in ('summary','next_action','status','attention')}
        step = next(s for s in value['steps'] if s['id'] == sid)
        attempt = step['attempts'][-1]
        from .handoff import blocking_checks
        failed_checks = [clean_summary(c.get('name')) for c in blocking_checks(handoff.get('checks', []))]
        compliance = (policy_workflow.handoff_compliance(value.get('policy_plan'), sid, purpose, handoff)
                      if result.get('ok') and policy_workflow.governed(value) else [])
        if compliance:
            attempt['policy_compliance'] = compliance
            failed_checks += policy_workflow.violations(compliance)
        checkpoint = policy_workflow.open_checkpoint(value, sid, purpose, request_id) if result.get('ok') else None
        step['status'] = ('needs_revision' if failed_checks else 'completed') if result.get('ok') else 'paused'
        attempt.update(status=step['status'], finished_at=utcnow(), validated=bool(result.get('ok')),
            runtime_image=clean_summary(result.get('runtime_image', ''), 512),
            delivery_record=delivery_summary(result.get('delivery_record')), quality_review=result.get('quality_review'),
            product_verified=bool(result.get('product_verified')),
            verified_products=result.get('verified_products', [])[:10],
            output_dir=result.get('output_dir') or attempt.get('output_dir', ''),
            output_files=(handoff.get('output_files') or result.get('available_files') or [])[:40],
            input_files=handoff.get('source_files', [])[:40],
            previews=handoff.get('previews', [])[:8], error=clean_summary(result.get('error', '')))
        if result.get('environment'):
            attempt['environment'] = {k:result['environment'].get(k) for k in ('id','core','tools','image_id','skills','skill_revision','version_names','versions')}
            actual={t:installed[t] for t in result['environment'].get('tools',[]) if t in installed}
            actual.update(result['environment'].get('version_names',{}))
            attempt['tool_environment']=scoped_file(workspace,'tool-environments/'+fingerprint(actual)+'.json',json.dumps(actual,sort_keys=True))
        if result.get('recovery'):
            attempt['recovery'] = result['recovery']
        attempt['failed_checks'] = failed_checks
        step['note'] = clean_summary('Controlli da valutare: ' + ', '.join(notes)) if notes else ''
        attention = failure_info(attempt['error']) if attempt['error'] else result.get('attention')
        value.update(status='review' if result.get('ok') else 'blocked', attention=attention,
            summary='Risultati disponibili: posso integrarli e migliorare la versione.' if result.get('ok') else attention['message'],
            next_action='Prepara o aggiorna una versione completa del prodotto usando i risultati disponibili.'
                if result.get('ok') else attention['action'], updated_at=utcnow())
        stale_contract=(value.get('acceptance') or {}).get('hash')!=context.get('contract')
        attempt['stale_request']=stale_contract
        newer_version=purpose=='delivery' and attempt.get('version_number',0)<value.get('selected_version_number',0)
        if purpose == 'delivery' and result.get('ok') and not stale_contract and not newer_version:
            value['selected_version_number']=attempt.get('version_number',0)
            exports = result.get('verified_products') or [f['path'] for f in
                product_files((result.get('delivery_record') or {}).get('files', []))]
            if exports:
                value['product_path'] = exports[0]
            issues = (result.get('delivery_record') or {}).get('issues', [])
            value.update(summary='Versione disponibile; sorgenti da correggere.' if issues else 'Versione completa disponibile per la revisione.',
                next_action=clean_summary(issues[0]) if issues else 'Valutare il risultato rispetto al brief prima di dichiararlo pronto.')
        if result.get('quality_review'):
            review = result['quality_review']
            value.update(summary='Revisione del risultato completata.' if review['status'] == 'passed' else 'Versione disponibile; qualità ancora da valutare o correggere.',
                next_action='Confermare la consegna della versione revisionata.' if review['status'] == 'passed'
                else 'Consulta il rapporto: correggi solo i difetti osservati. Se manca visione/ascolto, valuta la versione disponibile senza rigenerarla.')
            corrections = review.get('revision_actions', [])
            if review['status'] != 'passed' and corrections:
                value['next_action'] = clean_summary(corrections[0]['action'])
        if failed_checks and result.get('ok'):
            value.update(status='review', summary='File conservati; la lavorazione richiede correzioni.',
                         next_action='Rivaluta il metodo e correggi le verifiche fallite: ' + ', '.join(failed_checks))
            recovery = method_recovery(workspace, value)
            if recovery:
                value['method_recovery'] = recovery
                result['method_recovery'] = recovery
        if result.get('quality_review'):
            from .control_memory import continuation
            followup = continuation(result['quality_review'])
            if followup and followup['action'] in ('continue_production', 'request_user_verification'):
                value.update(status='review', next_action=followup['instruction'])
                value['summary'] = ('Prova mirata superata; prodotto finale da completare.'
                    if followup['action'] == 'continue_production' else 'Versione disponibile; serve la tua verifica dei controlli non disponibili.')
        if stale_contract or newer_version:value.update(presentation)
        if (value.get('user_control') or {}).get('deliver_now'):
            value.update(summary='Consegna richiesta: file disponibili con i limiti registrati' if result.get('ok') else 'Chiusura richiesta: nessun nuovo prodotto verificato',next_action='Presenta i risultati disponibili e attendi nuove istruzioni dell’utente')
        atomic_json(folder / 'project.json', value)
    if checkpoint:
        result['checkpoint'] = policy_workflow.checkpoint_instruction(checkpoint)
    violations = policy_workflow.violations(compliance)
    if violations:
        record_policy_event(workspace, value, 'Handoff non conforme al Policy Plan', 'failed',
                            detail=sid + ': ' + ', '.join(violations))
        result['policy_violations'] = violations
    if compliance:
        result['policy_compliance'] = compliance
    if (result.get('quality_review') or {}).get('status') == 'passed' and not stale_contract and not newer_version:
        reconcile_completion(workspace)
    if result.get('user_requested_delivery'):
        result['instruction']='L’utente ha chiesto la consegna: presenta file e limiti e fermati senza nuove deleghe.'
    result.update(activity={'id': sid, 'status': step['status']}, review_notes=notes)
    if attention:
        result['attention'] = attention
    return json.dumps(result, ensure_ascii=False)


def read_results(value, workspace=None):
    """A bounded catalog of actual handoffs and partial work, not all attempt logs."""
    results = []
    for step in value['steps']:
        seen = set()
        for attempt in visible_attempts(step, value.get('product_path', '')):
            paths = [p for p in available_paths(workspace, attempt) if p not in seen][:12]
            if paths or attempt.get('output_dir'):
                results.append({'activity': step['id'], 'agent': step['agent'], 'validated': attempt.get('validated',
                    attempt.get('status') == 'completed'), 'output_dir': attempt.get('output_dir'), 'files': paths,
                    'at': attempt.get('finished_at', '')})
            seen.update(paths)
    return sorted(results, key=lambda r: (value.get('product_path') in r['files'], r['at']), reverse=True)[:20]


def sync_project_context(workspace, roles=None, memory=None, experience_root=None,skill_policy=None):
    """Persist project memory and compile only the skills needed by its live roles."""
    apps = applications()
    specs = validate_roles(roles, apps) if roles is not None else None
    if memory is not None and (not isinstance(memory, dict) or len(json.dumps(memory).encode()) > 40000):
        raise ValueError('La memoria richiede un oggetto JSON entro 40 KiB; usa file referenziati per contenuti lunghi')
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            return
        current = json.loads(read_document(workspace, value['memory'])) if value.get('memory') else {}
        if memory is not None:
            current.update(redact_memory(memory))
        if value.get('outcome'):
            current['project_outcome'] = value['outcome']
        current['user_direction'] = value.get('user_direction')
        current['user_control'] = value.get('user_control')
        if value.get('strategy'):
            current['method_selection'] = value['strategy']['record']
        serialized = json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2)
        if len(serialized.encode()) > 40000:
            raise ValueError('Memoria troppo grande: conserva testi e asset nei file e indica i riferimenti')
        memo = scoped_file(workspace, 'memory/' + fingerprint(current) + '.json', serialized)
        specs = specs if specs is not None else value.get('role_specs', [])
        from .skill_composition import bind
        old={role['id']:role for role in value.get('roles',[])}
        resolved=[bind(spec,skill_policy,old.get(spec['id'])) for spec in specs]
        if experience_root is not None:
            from .experience import snapshot
            experiences = {spec['id']: snapshot(workspace, experience_root, [{**spec,'tools':spec.get('resolved_tools',spec['tools'])}], apps) for spec in resolved}
        else:
            experiences = {}
        compiled = [compile_role(workspace, spec, value.get('acceptance'), memo, apps, experiences.get(spec['id'])) for spec in resolved]
        if value.get('roles') == compiled and value.get('memory') == memo:
            return
        value.update(role_specs=specs, roles=compiled, memory=memo)
        atomic_json(folder / 'project.json', value)


def request_project_delivery(workspace):
    with locked(workspace) as folder:
        value=load(folder,workspace)
        if not value:raise ValueError('Progetto non disponibile')
        control=value.get('user_control') or {}
        value['user_control']={**control,'deliver_now':True,'updated_at':utcnow()}
        value.update(summary='Consegna richiesta: chiudo gli incarichi e verifico i file disponibili',next_action='Mostrare i risultati e attendere l’utente')
        atomic_json(folder/'project.json',value)
        return value['user_control']
