"""Policy-driven project lifecycle, enforced by the runtime rather than the prompt.

Brief -> (Execution Plan + Policy Plan) -> policy-aware task execution ->
final multi-policy validation -> delivery. Projects created before the Policy
Book keep their original behaviour and report the ``legacy`` phase.
"""
from . import policy_book
from .progress import clean_summary

GOVERNANCE = {'model': 'policy_book', 'version': 1}
PRODUCTION = ('work', 'preview', 'integration', 'delivery')
SETTLED = ('completed', 'skipped', 'review')


def governed(value):
    return (value or {}).get('governance', {}).get('model') == GOVERNANCE['model']


def ensure_plan(value):
    """Pin a system plan when there is nothing to choose; add new mandatory sheets.

    Returns an audit description when the plan changed, otherwise None.
    """
    plan = value.get('policy_plan')
    if plan and not policy_book.missing_mandatory(plan):
        return None
    if plan:
        kept = [{'id': s['id'], 'reason': s['reason'], 'steps': [x for x in s['steps'] if x in {t['id'] for t in value['steps']}]}
                for s in plan['sheets'] if not s['mandatory']]
        value['policy_plan'] = policy_book.build_plan(kept, value['steps'], selected_by=plan['selected_by'])
        return 'Policy Plan aggiornato con le sheet diventate obbligatorie'
    value['policy_plan'] = policy_book.build_plan([], value['steps'], selected_by='system')
    return 'Policy Plan creato con le sole sheet obbligatorie' if policy_book.settled(value['policy_plan']) else None


def phase(value):
    """Where the project stands; derived from recorded facts, never from the model."""
    from .project_brief import briefing_issue
    if not value:
        return 'briefing'
    if not governed(value):
        return 'legacy'
    if value.get('status') == 'ready':
        return 'delivered'
    if not value.get('outcome') or briefing_issue(value['outcome']):
        return 'briefing'
    steps = [s for s in value['steps'] if s.get('kind') != 'validation']
    if not steps or not policy_book.settled(value.get('policy_plan')):
        return 'planning'
    if any(s['status'] not in SETTLED for s in steps) or not value.get('product_path'):
        return 'execution'
    return 'validation' if (value.get('policy_validation') or {}).get('status') != 'passed' else 'delivery'


def require_production(value):
    """Gate for every production assignment of a governed project."""
    if not governed(value):
        return
    plan = value.get('policy_plan')
    if not policy_book.settled(plan):
        optional = ', '.join((plan or {}).get('optional_available', []))
        raise ValueError('Prima degli incarichi completa il Policy Plan accanto all’Execution Plan: '
                         'usa harness_plan(policies_json) scegliendo le sheet facoltative pertinenti (' + optional +
                         ') con una motivazione, oppure [] se nessuna si applica. Le sheet obbligatorie sono incluse dal sistema.')


def applicable(plan, step_id, purpose):
    if not plan or purpose not in PRODUCTION:
        return []
    return [s for s in plan['sheets'] if purpose in s['applies_to'] and (not s['steps'] or step_id in s['steps'])]


def task_brief(plan, step_id, purpose, sheet=None):
    """The policy part of an assignment: rules and declarations it must satisfy."""
    if sheet is not None and sheet['final_checks'] == 'acceptance':
        return ('\n\nValidazione finale della policy sheet «' + sheet['title'] + '»: revisione separata del prodotto finito '
                'rispetto al contratto di accettazione. Scrivi quality-review.json coprendo ogni requisito del contratto con '
                'requirement_id, metodo pertinente ed evidenza; non modificare il prodotto.')
    if sheet is not None:
        return ('\n\nValidazione finale della policy sheet «' + sheet['title'] + '» (id ' + sheet['id'] + '). '
                'Esamina il prodotto finito senza modificarlo e scrivi quality-review.json: ogni criterio usa '
                'requirement_id uguale all’id del controllo, method indicato e evidenza osservabile. '
                'Un controllo non eseguibile resta not_run, mai passed.\nControlli:\n' +
                '\n'.join('- ' + c['id'] + ' [' + c['method'] + (', critico' if c['critical'] else '') + ']: ' + c['requirement']
                          for c in sheet['final_checks']))
    sheets = applicable(plan, step_id, purpose)
    if not sheets:
        return ''
    lines = ['\n\nPolicy Plan del progetto (vincolante, verificato dal runtime):']
    for item in sheets:
        lines.append('Sheet «' + item['title'] + '» (' + item['id'] + '):')
        lines += ['- ' + rule for rule in item['rules']]
    checks = [(s, c) for s in sheets for c in s['handoff_checks']]
    if checks:
        lines.append('Nei checks dell’handoff includi per ciascun controllo un elemento con name, status, evidence '
                     'e policy_check uguale a «sheet.controllo». Un controllo critico mancante o non superato '
                     'riporta l’attività in revisione:')
        lines += ['- ' + s['id'] + '.' + c['id'] + (' (critico)' if c['critical'] else '') + ': ' + c['requirement']
                  for s, c in checks]
    return '\n'.join(lines)


def handoff_compliance(plan, step_id, purpose, handoff):
    """Match the declared handoff checks against the plan's required checks."""
    declared = {}
    for check in (handoff or {}).get('checks', []):
        if isinstance(check, dict) and isinstance(check.get('policy_check'), str) and check.get('scope', 'current') == 'current':
            declared.setdefault(check['policy_check'], check)
    result = []
    for sheet in applicable(plan, step_id, purpose):
        for check in sheet['handoff_checks']:
            key = sheet['id'] + '.' + check['id']
            found = declared.get(key)
            result.append({'sheet': sheet['id'], 'check': check['id'], 'critical': check['critical'],
                           'status': found['status'] if found else 'not_run',
                           'evidence': clean_summary(found.get('evidence') if found else 'Controllo non dichiarato nell’handoff')})
    return result


def violations(compliance):
    return ['Policy ' + c['sheet'] + '.' + c['check'] for c in compliance if c['critical'] and c['status'] != 'passed']


def sheet_reviews(value, sheet):
    """Review attempts that validated this sheet, newest first."""
    return sorted((a for s in value['steps'] for a in s['attempts']
                   if a.get('policy_review') == sheet['id'] and a.get('quality_review')),
                  key=lambda a: a.get('finished_at', ''), reverse=True)


def sheet_verdict(workspace, value, sheet, target_hash):
    """Verdict of one sheet on the product with this hash, from the recorded reviews."""
    from . import projects
    if sheet['final_checks'] == 'acceptance':
        review = projects.standard_review(workspace, value, target_hash)
        attempts = projects.standard_reviews(value)
    else:
        expected = policy_book.contract(sheet, None)['hash']
        attempts = sheet_reviews(value, sheet)
        review = next((a['quality_review'] for a in attempts
                       if a['quality_review'].get('sha256') == target_hash
                       and a['quality_review'].get('contract_hash') == expected), None)
    if review is None:
        return {'status': 'pending'}
    attempt = next((a for a in attempts if a['quality_review'].get('report_path') == review.get('report_path')), {})
    return {'status': {'passed': 'passed', 'needs_revision': 'failed'}.get(review.get('status'), 'needs_review'),
            'report_path': review.get('report_path', ''), 'reviewed_at': attempt.get('finished_at', ''),
            'findings': [{k: c.get(k) for k in ('requirement_id', 'status', 'critical', 'method')}
                         | {'criterion': clean_summary(c.get('criterion'), 200), 'evidence': clean_summary(c.get('evidence'), 240)}
                         for c in review.get('criteria', []) if c.get('status') != 'passed'][:8]}


def validation(workspace, value):
    """Aggregate verdict of every sheet on the current product, recomputed from files."""
    from . import projects
    from .source_packages import digest
    plan = value.get('policy_plan')
    target = projects.artifact_path(workspace, value.get('product_path', ''))
    integrity = projects.delivery_integrity(workspace, value, target)
    report = {'product_path': value.get('product_path', ''), 'plan_hash': (plan or {}).get('hash'),
              'integrity': {'status': 'failed' if integrity else 'passed', 'issue': integrity or ''}, 'sheets': []}
    if not plan or integrity:
        report['status'] = 'blocked'
        return report
    target_hash = report['sha256'] = digest(target)
    for sheet in plan['sheets']:
        verdict = sheet_verdict(workspace, value, sheet, target_hash)
        report['sheets'].append({'id': sheet['id'], 'title': sheet['title'], 'depends_on': sheet['depends_on'],
                                 **{k: verdict[k] for k in ('status', 'report_path', 'findings') if k in verdict}})
    states = {s['status'] for s in report['sheets']}
    report['status'] = ('passed' if states == {'passed'} else 'failed' if 'failed' in states
                        else 'pending' if 'pending' in states else 'needs_review')
    return report


def live(workspace, value):
    """What governs this project right now, computed from files for the chat panel."""
    if not governed(value):
        return {'phase': 'legacy'}
    from . import projects
    from .source_packages import digest
    plan = value.get('policy_plan')
    result = {'phase': phase(value), 'settled': policy_book.settled(plan), 'sheets': []}
    if not plan:
        return result
    result.update(planned_at=plan.get('created_at', ''), selected_by=plan.get('selected_by'),
                  optional_available=plan.get('optional_available', []))
    target = projects.artifact_path(workspace, value.get('product_path', ''))
    if target:
        integrity = projects.delivery_integrity(workspace, value, target)
        result['product'] = {'path': value.get('product_path', ''), 'integrity': 'failed' if integrity else 'passed', 'issue': integrity or ''}
    target_hash = digest(target) if target else None
    compliance = [c for s in value['steps'] if s.get('kind') != 'validation' and s['attempts']
                  for c in s['attempts'][-1].get('policy_compliance', [])]
    for sheet in plan['sheets']:
        verdict = sheet_verdict(workspace, value, sheet, target_hash) if target_hash else {'status': 'pending'}
        declared = [c for c in compliance if c['sheet'] == sheet['id']]
        result['sheets'].append({**{k: sheet[k] for k in ('id', 'title', 'version', 'mandatory', 'reason', 'steps', 'depends_on')},
            'final': 'acceptance' if sheet['final_checks'] == 'acceptance' else len(sheet['final_checks']),
            'handoff': {'required': len(sheet['handoff_checks']), 'declared': sum(c['status'] == 'passed' for c in declared),
                        'violations': [c['check'] for c in declared if c['critical'] and c['status'] != 'passed']},
            **verdict})
    saved = value.get('policy_validation') or {}
    if saved:
        result['last_validation'] = {'at': saved.get('at', ''), 'status': saved.get('status')}
    return result


def waves(sheets):
    """Independent sheets run together; a dependent sheet waits for its prerequisites."""
    remaining, done, result = list(sheets), set(), []
    while remaining:
        ready = [s for s in remaining if set(s['depends_on']) <= done]
        if not ready:
            raise ValueError('Dipendenze tra policy sheet non risolvibili')
        result.append(ready)
        done.update(s['id'] for s in ready)
        remaining = [s for s in remaining if s not in ready]
    return result


def view(workspace, value):
    """Board/coordinator summary of the governance state."""
    if not governed(value):
        return {'phase': 'legacy'}
    plan = value.get('policy_plan')
    result = {'phase': phase(value)}
    if plan:
        result['policy_plan'] = {'settled': policy_book.settled(plan), 'sheets': [s['id'] for s in plan['sheets']]}
        if plan.get('optional_available') and not policy_book.settled(plan):
            result['policy_plan']['optional_available'] = plan['optional_available']
    if value.get('policy_validation'):
        saved = value['policy_validation']
        result['policy_validation'] = {k: saved.get(k) for k in ('status', 'product_path', 'sha256', 'plan_hash', 'at', 'integrity')} | {
            'sheets': [{k: s.get(k) for k in ('id', 'title', 'status')} for s in saved.get('sheets', [])]}
    return result
