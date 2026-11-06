"""Preserve actionable review feedback and bind before/after claims to files."""
from pathlib import Path

try:
    from .acceptance import capabilities
except ImportError:
    from acceptance import capabilities

STRATEGIES = {'revise', 'change_method', 'verify', 'missing_dependency'}


def findings(value, criteria):
    """Separate demonstrated blockers from advice; preserve legacy reports."""
    version = value.get('review_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Revisione: review_version 1 o 2')
    raw = value.get('findings', [])
    if not isinstance(raw, list) or len(raw) > 20:
        raise ValueError('Revisione: al massimo 20 rilievi')
    known = {c.get('requirement_id') for c in criteria if c.get('requirement_id')}
    result = []
    for item in raw:
        if not isinstance(item, dict) or item.get('severity') not in ('blocking', 'advisory', 'uncertain'):
            raise ValueError('Rilievo: severity blocking, advisory o uncertain')
        rid = item.get('requirement_id')
        if rid is not None and rid not in known:
            raise ValueError('Rilievo: requisito sconosciuto')
        for key in ('location', 'evidence', 'impact'):
            if not isinstance(item.get(key), str) or not item[key].strip() or len(item[key]) > 2000:
                raise ValueError('Rilievo: posizione, prova osservata e impatto obbligatori')
        if item['severity'] == 'blocking' and not rid:
            raise ValueError('Un rilievo bloccante deve riguardare un requisito concordato')
        result.append({k: item[k] for k in ('severity', 'location', 'evidence', 'impact')})
        if rid:
            result[-1]['requirement_id'] = rid
    if version == 2:
        failed = {c.get('requirement_id') for c in criteria if c['status'] == 'failed'
                  and c.get('scope') != 'supplementary'}
        blockers = {f.get('requirement_id') for f in result if f['severity'] == 'blocking'}
        if failed - blockers:
            raise ValueError('Revisione v2: un requisito fallito richiede un rilievo blocking con posizione, prova e impatto; un consiglio non basta')
        if blockers - failed:
            raise ValueError('Revisione v2: un rilievo blocking non può accompagnare un requisito approvato o non verificato')
    return result


def correction_focus(project):
    """Keep unresolved defects from the latest review visible to the next worker.

    Count distinct products, not repeated reviews of the same bytes. A different
    contract cannot establish a plateau on the current user's requirements.
    """
    try:
        from .acceptance import requirement_verdicts
    except ImportError:
        from acceptance import requirement_verdicts
    contract = (project.get('acceptance') or {}).get('hash')
    reviews = [(a.get('finished_at', ''), a['quality_review']) for s in project.get('steps', [])
               for a in s.get('attempts', []) if a.get('validated') and a.get('quality_review')
               and (not contract or a['quality_review'].get('contract_hash') == contract)]
    reviews.sort(key=lambda item: item[0])
    if not reviews:
        return []
    latest = reviews[-1][1]
    scope = latest.get('checkpoint')
    result = []
    for verdict in requirement_verdicts(latest.get('criteria', [])):
        rid = verdict['requirement_id']
        if scope and rid not in scope['requirement_ids']:
            continue  # Final-only gaps are not evidence that this experiment stalled.
        if verdict['status'] != 'failed':
            continue
        products = set()
        chain = {latest.get('sha256')}
        for _, review in reversed(reviews):
            if review.get('sha256') not in chain:
                continue  # Different contributions are not successive versions.
            state = next((v['status'] for v in requirement_verdicts(review.get('criteria', [])) if v['requirement_id'] == rid), None)
            if state != 'failed':
                break
            if review.get('sha256'):
                products.add(review['sha256'])
            baseline = (review.get('comparison') or {}).get('baseline_sha256')
            if baseline:
                chain.add(baseline)
        action = next((a for a in latest.get('revision_actions', []) if a.get('requirement_id') == rid), {})
        criterion = next(c for c in latest['criteria'] if c.get('requirement_id') == rid and c.get('status') == 'failed')
        result.append({'requirement_id': rid, 'criterion': criterion['criterion'][:200],
                       'action': action.get('action', 'Ispeziona il difetto e verifica una correzione mirata.')[:500],
                       'priority': action.get('priority', 2), 'failed_products': len(products),
                       'reassess_role': len(products) >= 2 or action.get('strategy') == 'change_method',
                       'report_path': latest.get('report_path', '')})
    return sorted(result, key=lambda r: (not r['reassess_role'], r['priority']))[:3]


def actions(value, criteria):
    raw = value.get('revision_actions')
    legacy = raw is None
    if legacy:
        raw = value.get('targeted_corrections', [])
    if not isinstance(raw, list) or len(raw) > 12:
        raise ValueError('Revisione: al massimo 12 azioni di correzione concrete')
    known = {c.get('requirement_id') for c in criteria if c.get('requirement_id')}
    result = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('Azione di correzione non valida')
        rid, action = item.get('requirement_id', ''), item.get('action', '')
        strategy, priority = item.get('strategy', 'revise'), item.get('priority', 2)
        reason = item.get('reason', '')
        if (not isinstance(rid, str) or rid and rid not in known or not isinstance(action, str)
                or not action.strip() or len(action) > 1200 or not isinstance(reason, str) or len(reason) > 1200
                or not isinstance(strategy, str) or strategy not in STRATEGIES or type(priority) is not int or priority not in (1, 2, 3)):
            raise ValueError('Correzione: requisito esistente, azione concreta, strategia e priorità 1–3')
        result.append({'requirement_id': rid, 'action': action.strip(), 'reason': reason,
                       'strategy': strategy, 'priority': priority})
    return sorted(result, key=lambda a: a['priority'])


def comparison(value, criteria, handoff, workspace, target, digest, engine):
    baseline = value.get('baseline_path')
    if not baseline:
        if value.get('comparison'):
            raise ValueError('Il confronto richiede baseline_path effettivamente letto')
        return None
    if not isinstance(baseline, str):
        raise ValueError('baseline_path deve essere un percorso')
    root = Path(workspace).resolve(); path = Path(baseline).resolve()
    if (not path.is_relative_to(root) or path == target or not path.is_file()
            or str(path) not in handoff['source_files']):
        raise ValueError('Confronto: versione precedente distinta, esistente e letta in source_files')
    before, after = digest(path), digest(target)
    items = value.get('comparison', [])
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise ValueError('Confronto: da 1 a 20 requisiti osservati prima/dopo')
    known = {c.get('requirement_id'): c for c in criteria if c.get('requirement_id')}
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Confronto non valido')
        rid, status = item.get('requirement_id'), item.get('status')
        evidence = item.get('evidence')
        if (not isinstance(rid, str) or rid not in known or rid in seen or status not in ('improved', 'unchanged', 'regressed', 'not_verified')
                or not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 2000):
            raise ValueError('Confronto: requisito unico esistente, stato e prova concreta obbligatori')
        seen.add(rid)
        if status == 'improved' and before == after:
            raise ValueError('Non dichiarare migliorato un prodotto con byte identici alla versione precedente')
        criterion = known[rid]
        if not capabilities(engine).get(criterion.get('method'), False) or criterion.get('status') == 'not_run':
            status = 'not_verified'
            evidence = 'Metodo di osservazione non eseguito o non disponibile; il miglioramento non è verificato.'
        result.append({'requirement_id': rid, 'status': status, 'evidence': evidence})
    return {'baseline_path': str(path), 'baseline_sha256': before, 'product_sha256': after,
            'criteria': result, 'note': 'Confronto dello specialista su file identificati; non certificazione oggettiva di qualità.'}
