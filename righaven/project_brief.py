"""Describe a project's intended result without profession or file-format catalogs."""
import json
from .project_skills import request_text
from .progress import clean_summary


def validate_outcome(value):
    if not isinstance(value, dict):
        raise ValueError('Il risultato atteso richiede un oggetto JSON')
    fields = {'title': 120, 'result': 2000, 'format': 500, 'use': 1000, 'quality': 1000}
    if set(value) - set(fields) - {'constraints', 'assumptions', 'questions'}:
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
    if not result['questions'] and (not result['result'] or not result['format']):
        raise ValueError('Definisci risultato e forma della consegna oppure registra le domande ancora aperte')
    if len(json.dumps(result, ensure_ascii=False).encode()) > 16000:
        raise ValueError('Scheda del risultato troppo grande: conserva i dettagli nei documenti della richiesta')
    return result


def briefing_issue(outcome):
    if not outcome or not outcome.get('result') or not outcome.get('format'):
        return 'Prima di produrre definisci risultato atteso e forma della consegna con harness_plan(outcome_json). Chiedi all’utente soltanto le scelte mancanti che cambiano il prodotto; non decidere in silenzio un formato sostanzialmente diverso.'
    if outcome.get('questions'):
        return 'Attendi le risposte alle domande sul risultato prima di avviare gli incarichi. Poi aggiorna outcome_json con le scelte effettive e questions vuoto.'
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
