"""Describe a project's intended result without profession or file-format catalogs."""
import json
from .project_skills import request_text
from .progress import clean_summary


def validate_outcome(value):
    if not isinstance(value, dict):
        raise ValueError('Il risultato atteso richiede un oggetto JSON')
    fields = {'title': 120, 'result': 2000, 'format': 500, 'use': 1000, 'quality': 1000}
    if set(value) - set(fields) - {'constraints', 'assumptions', 'questions', 'tool_options'}:
        raise ValueError('Campi del risultato atteso non riconosciuti')
    result = {}
    for key, limit in fields.items():
        text = value.get(key, '')
        if not isinstance(text, str) or len(text) > limit:
            raise ValueError('Descrivi sinteticamente risultato, formato, uso e qualità attesa')
        result[key] = request_text(text.strip())
    for key in ('constraints', 'assumptions', 'questions'):
        items = value.get(key, [])
        if (not isinstance(items, list) or len(items) > (3 if key == 'questions' else 8)
                or any(not isinstance(s, str) or not s.strip() or len(s) > 600 for s in items)):
            raise ValueError('Usa al massimo tre domande decisive e liste brevi di vincoli e ipotesi')
        result[key] = [request_text(s.strip()) for s in items]
    result['tool_options'] = validate_tool_options(value.get('tool_options', []))
    if not result['questions'] and (not result['result'] or not result['format']):
        raise ValueError('Definisci risultato e forma della consegna oppure registra le domande ancora aperte')
    if len(json.dumps(result, ensure_ascii=False).encode()) > 16000:
        raise ValueError('Scheda del risultato troppo grande: conserva i dettagli nei documenti della richiesta')
    return result


SLUG = __import__('re').compile(r'[a-z][a-z0-9_-]{0,39}\Z')


def validate_tool_options(decisions):
    """Tool alternatives the user chooses from: pros, cons and a recommendation, never a silent pick."""
    from .state import applications
    known = {a['id'] for a in applications()}
    if not isinstance(decisions, list) or len(decisions) > 4:
        raise ValueError('tool_options: al massimo quattro decisioni sugli strumenti')
    result, seen = [], set()
    for decision in decisions:
        allowed = {'id', 'decision', 'options', 'recommended', 'recommendation_reason', 'chosen'}
        if (not isinstance(decision, dict) or set(decision) - allowed or not isinstance(decision.get('id'), str)
                or not SLUG.fullmatch(decision['id']) or decision['id'] in seen
                or not isinstance(decision.get('decision'), str) or not decision['decision'].strip()):
            raise ValueError('tool_options: ogni decisione richiede id, decision, options, recommended e recommendation_reason')
        seen.add(decision['id'])
        options = decision.get('options')
        if not isinstance(options, list) or not 2 <= len(options) <= 4:
            raise ValueError('tool_options: presenta da due a quattro alternative per ogni decisione')
        clean, ids = [], set()
        for option in options:
            if (not isinstance(option, dict) or set(option) - {'id', 'label', 'tools', 'pros', 'cons'}
                    or not isinstance(option.get('id'), str) or not SLUG.fullmatch(option['id']) or option['id'] in ids
                    or not isinstance(option.get('label'), str) or not option['label'].strip()):
                raise ValueError('tool_options: ogni alternativa richiede id, label, pros e cons')
            tools = option.get('tools', [])
            if not isinstance(tools, list) or any(t not in known for t in tools):
                raise ValueError('tool_options: tools elenca programmi del catalogo')
            lists = {k: option.get(k) for k in ('pros', 'cons')}
            if any(not isinstance(v, list) or not v or len(v) > 5 or any(not isinstance(x, str) or not x.strip() or len(x) > 300 for x in v)
                   for v in lists.values()):
                raise ValueError('tool_options: indica per ogni alternativa almeno un pregio e un difetto concreti')
            ids.add(option['id'])
            clean.append({'id': option['id'], 'label': clean_summary(option['label'], 140), 'tools': sorted(set(tools)),
                          **{k: [clean_summary(x, 300) for x in v] for k, v in lists.items()}})
        reason = decision.get('recommendation_reason', '')
        if decision.get('recommended') not in ids or not isinstance(reason, str) or not reason.strip():
            raise ValueError('tool_options: consiglia una delle alternative e motiva il consiglio; la scelta resta all’utente')
        chosen = decision.get('chosen', '')
        if chosen not in ('', *ids):
            raise ValueError('tool_options: chosen deve essere una delle alternative presentate')
        result.append({'id': decision['id'], 'decision': clean_summary(decision['decision'], 200), 'options': clean,
                       'recommended': decision['recommended'], 'recommendation_reason': clean_summary(reason, 600), 'chosen': chosen})
    return result


def rejected_tools(outcome):
    """Programs only in alternatives the user did not choose."""
    rejected = set()
    for decision in (outcome or {}).get('tool_options', []):
        if decision.get('chosen'):
            kept = next(o['tools'] for o in decision['options'] if o['id'] == decision['chosen'])
            rejected |= {t for o in decision['options'] if o['id'] != decision['chosen'] for t in o['tools']} - set(kept)
    return rejected


def briefing_issue(outcome):
    if not outcome or not outcome.get('result') or not outcome.get('format'):
        return 'Prima di produrre definisci risultato atteso e forma della consegna con harness_plan(outcome_json). Chiedi all’utente soltanto le scelte mancanti che cambiano il prodotto; non decidere in silenzio un formato sostanzialmente diverso.'
    if outcome.get('questions'):
        return 'Attendi le risposte alle domande sul risultato prima di avviare gli incarichi. Poi aggiorna outcome_json con le scelte effettive e questions vuoto.'
    open_choices = [d['decision'] for d in outcome.get('tool_options', []) if not d.get('chosen')]
    if open_choices:
        return ('Presenta all’utente le alternative sugli strumenti (' + '; '.join(open_choices) + ') con pregi, difetti e il tuo consiglio motivato, '
                'chiedi la scelta con ask_clarification e registra chosen solo dopo la sua risposta. Non scegliere al posto dell’utente.')
    return None


def orientation(value):
    """Actual activity counts, not an invented percentage or fixed production pipeline."""
    all_steps = value.get('steps', [])
    active_roles = {r['id'] for r in value.get('roles', [])}
    # Retired roles stay in history; a live worker stays visible even if the
    # coordinator changes the role set while it is running. No activity is deleted.
    steps = [s for s in all_steps if not active_roles or not s.get('role_id')
             or s['role_id'] in active_roles or s['status'] == 'running']
    history = [s for s in all_steps if s not in steps]
    counts = {state: sum(s['status'] == state for s in steps)
              for state in ('pending', 'running', 'completed', 'paused', 'review', 'needs_revision', 'skipped')}
    current = []
    roles = {}
    for step in all_steps:
        for index, attempt in enumerate(step.get('attempts', [])):
            rid = attempt.get('role_id')
            if not rid:
                continue
            usage = roles.setdefault(rid, {'attempts': 0, 'completed': 0, 'running': 0})
            usage['attempts'] += 1
            usage['completed'] += int(attempt.get('status') == 'completed')
            usage['running'] += int(step['status'] == 'running' and index == len(step['attempts']) - 1)
        if step['status'] != 'running':
            continue
        attempt = (step.get('attempts') or [{}])[-1]
        current.append({'id': step['id'], 'goal': clean_summary(step['goal']), 'role_id': attempt.get('role_id') or step.get('role_id', ''),
                        'task': clean_summary(attempt.get('task', step['goal']), 1500)})
    return {'active_step_ids': [s['id'] for s in steps], 'history_step_ids': [s['id'] for s in history],
            'history_count': len(history), 'counts': counts, 'total': len(steps) - counts['skipped'], 'current': current, 'roles': roles,
            'remaining': [{'id': s['id'], 'goal': clean_summary(s['goal']), 'status': s['status']} for s in steps
                          if s['status'] in ('pending', 'paused', 'review', 'needs_revision')],
            'needs_briefing': bool(briefing_issue(value.get('outcome')))}
