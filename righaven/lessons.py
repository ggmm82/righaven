"""Portable procedural lessons, kept separate from project-specific evidence."""
import json
from pathlib import Path
import re
from .acceptance import fingerprint
from .progress import utcnow
from .project_skills import redact_memory
from .state import atomic_json

ID = re.compile(r'[a-f0-9]{64}\Z')
SPECIFIC = re.compile(r'/(?:mnt|root|tmp|workspace|home)/|\b[a-f0-9]{64}\b|\b[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\b', re.I)


def validate(value):
    if not isinstance(value, dict) or set(value) - {'title', 'applies_when', 'procedure', 'verification', 'limits', 'tools', 'category'}:
        raise ValueError('La lezione contiene solo titolo, condizioni, procedura, verifiche, limiti e strumenti pertinenti')
    clean = {}
    for key, cap in (('title', 140), ('applies_when', 1000), ('limits', 1000)):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > cap:
            raise ValueError('Descrivi una lezione generale con condizioni e limiti, senza fatti del progetto')
        clean[key] = text.strip()
    for key in ('procedure', 'verification'):
        items = value.get(key)
        if not isinstance(items, list) or not 1 <= len(items) <= 6 or any(not isinstance(s, str) or not s.strip() or len(s) > 600 for s in items):
            raise ValueError('Procedura e verifiche richiedono da uno a sei passi generali')
        clean[key] = [s.strip() for s in items]
    tools = value.get('tools', [])
    if not isinstance(tools, list) or len(tools) > 4 or any(not isinstance(t, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', t) for t in tools):
        raise ValueError('Strumenti della lezione non validi; lista vuota per un principio indipendente dalle CLI')
    clean['tools'] = sorted(set(tools))
    if 'category' in value:
        if value['category'] not in ('tool_operation', 'production_method'):
            raise ValueError('Categoria: tool_operation oppure production_method')
        if value['category'] == 'tool_operation' and not tools:
            raise ValueError('Una lezione tecnica deve indicare gli strumenti pertinenti')
        clean['category'] = value['category']
    if SPECIFIC.search(json.dumps(clean, ensure_ascii=False)):
        raise ValueError('La lezione non deve contenere percorsi, hash o identificatori del progetto; restano nelle evidenze')
    if redact_memory(clean) != clean:
        raise ValueError('La lezione non deve contenere credenziali')
    return clean


def validate_impact(value=None):
    if value is None:
        return {'level': 'unknown', 'basis': 'hypothesis', 'reason': 'Impatto non ancora valutato'}
    if (not isinstance(value, dict) or set(value) != {'level', 'basis', 'reason'}
            or value['level'] not in ('major', 'minor', 'unknown')
            or value['basis'] not in ('measured', 'observed', 'hypothesis')
            or not isinstance(value['reason'], str) or not 5 <= len(value['reason'].strip()) <= 1000
            or redact_memory(value) != value):
        raise ValueError('Indica impatto major/minor/unknown, base measured/observed/hypothesis e motivazione verificabile; niente percentuali inventate')
    return {**value, 'reason': value['reason'].strip()}


def rank(record):
    impact = record.get('basis', {}).get('impact') or record.get('impact') or {}
    level, basis = impact.get('level', 'unknown'), impact.get('basis', 'hypothesis')
    # Observed small benefits precede unproven promises of a large gain.
    return {('major', 'measured'): 0, ('major', 'observed'): 1, ('minor', 'measured'): 2,
            ('minor', 'observed'): 3, ('major', 'hypothesis'): 4, ('minor', 'hypothesis'): 5}.get((level, basis), 6)


def entries(root):
    folder = Path(root) / 'lessons'
    if folder.is_symlink():
        raise ValueError('Archivio lezioni non valido')
    result = []
    for path in folder.glob('*.json'):
        if not ID.fullmatch(path.stem) or path.is_symlink() or path.stat().st_size > 16000:
            continue
        try:
            record = json.loads(path.read_text())
            if isinstance(record.get('at'), str) and record['id'] == path.stem and fingerprint(record['basis']) == path.stem:
                validate(record['basis']['lesson'])
                result.append(record)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return sorted(result, key=lambda r: (r['at'], r['id']), reverse=True)


def learn(root, source_ids, value, impact=None):
    from .experience import entries as observations, locked, disabled
    lesson = validate(value)
    impact = validate_impact(impact)
    if not isinstance(source_ids, list) or not 1 <= len(source_ids) <= 6 or any(not isinstance(s, str) or not ID.fullmatch(s) for s in source_ids):
        raise ValueError('Indica da una a sei evidenze realmente conservate')
    with locked(root) as folder:
        sources = {r['id']: r['observation'] for r in observations(folder)}
        excluded = disabled(folder)
        if any(s not in sources or s in excluded for s in source_ids):
            raise ValueError('Evidenza assente o esclusa: non usarla come esperienza')
        if impact['basis'] == 'measured' and not any(sources[s].get('measurement') for s in source_ids):
            raise ValueError('Un impatto misurato richiede misure prima/dopo conservate; usa observed o hypothesis se non ci sono')
        tools = {}
        for tool in lesson['tools']:
            versions = {sources[s].get('tools', {}).get(tool) for s in source_ids} - {None}
            if len(versions) != 1:
                raise ValueError('Una lezione tecnica richiede la versione dello strumento nelle sue fonti')
            tools[tool] = versions.pop()
        basis = {'lesson': lesson, 'impact': impact, 'source_ids': sorted(set(source_ids)), 'tool_versions': tools,
                 'source_statuses': sorted({sources[s].get('status', 'unknown') for s in source_ids})}
        identifier = fingerprint(basis)
        path = folder / 'lessons' / (identifier + '.json')
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError('Percorso lezione non valido')
        path.parent.mkdir(exist_ok=True, mode=0o700)
        if not path.exists():
            record = {'id': identifier, 'at': utcnow(), 'basis': basis,
                      'notice': 'Metodo da accettare singolarmente o conoscenza tecnica da verificare automaticamente; le evidenze non garantiscono un risultato universale.'}
            if len(json.dumps(record, ensure_ascii=False, indent=2).encode()) + 1 > 16000:
                raise ValueError('Lezione troppo lunga: conserva una sola lezione sintetica alla volta')
            atomic_json(path, record)
        return identifier


def propose_findings(root, source_thread, limit=3):
    """Preserve generalized worker findings under their approval policy.

    Never invent a procedure from raw review facts. Existing lessons and source
    decisions win; the same recipe/version is not proposed again for each job.
    """
    from .experience import entries as observations, disabled
    existing = entries(root)
    covered = {s for r in existing for s in r['basis']['source_ids']} | disabled(root) | set(reviewed(root))
    known = {(fingerprint(r['basis']['lesson']), tuple(sorted(r['basis']['tool_versions'].items()))) for r in existing}
    verified = {(fingerprint(r['basis']['lesson']), tuple(sorted(r['basis']['tool_versions'].items())))
                for r in existing if r['id'] in accepted(root)}
    saved = []
    for record in sorted(observations(root), key=lambda r: rank(r['observation'])):
        source = record['observation']
        impact = source.get('impact') or {}
        tested_operation = (source.get('technical_validation', {}).get('status') == 'passed'
                            and (source.get('suggested_lesson') or {}).get('category') == 'tool_operation')
        if (record['id'] in covered or source.get('source_thread') != source_thread
                or source.get('kind') != 'sandbox_tool_use' or not source.get('evidence_files')
                or (not tested_operation and (impact.get('level') not in ('major', 'minor')
                    or impact.get('basis') not in ('observed', 'measured')))):
            continue
        try:
            lesson = validate(source.get('suggested_lesson'))
            identity = (fingerprint(lesson), tuple(sorted(source.get('tools', {}).items())))
            upgrade = (lesson.get('category') == 'tool_operation'
                       and source.get('technical_validation', {}).get('status') == 'passed')
            if identity in known and (not upgrade or identity in verified):
                continue
            saved.append(learn(root, [record['id']], lesson, impact))
            known.add(identity)
            if upgrade:
                verified.add(identity)
        except (ValueError, KeyError, TypeError):
            continue
        if len(saved) >= limit:
            break
    return saved


def pending(root, limit=6, *, source_thread=None, meaningful_only=False):
    from .experience import entries as observations, disabled
    covered = {s for r in entries(root) for s in r['basis']['source_ids']}
    excluded = disabled(root) | set(reviewed(root))
    return [{'id': r['id'], 'source_thread':r['observation'].get('source_thread'), 'criterion': r['observation'].get('criterion'),
             'evidence': r['observation'].get('evidence'), 'status': r['observation'].get('status'),
             'corrections': r['observation'].get('corrections', []), 'tools': r['observation'].get('tools', {}),
             'suggested_lesson': r['observation'].get('suggested_lesson'),
             'producer_method': r['observation'].get('producer_method'), 'procedure': r['observation'].get('procedure', []),
             'impact': r['observation'].get('impact'), 'measurement': r['observation'].get('measurement'),
             'evidence_files': r['observation'].get('evidence_files', []), 'limitations': r['observation'].get('limitations', [])}
            for r in sorted(observations(root), key=lambda r: rank(r['observation'])) if r['id'] not in covered and r['id'] not in excluded
            and (source_thread is None or r['observation'].get('source_thread')==source_thread)
            and (not meaningful_only or r['observation'].get('suggested_lesson')
                 or r['observation'].get('status') in ('failed','reported_failure','needs_generalization','preferred_by_user')
                 or r['observation'].get('corrections')
                 or (r['observation'].get('impact') or {}).get('level') in ('major','minor'))][:limit]


def reviewed(root):
    path = Path(root) / 'lesson-decisions.json'
    if path.is_symlink():
        raise ValueError('Indice lezioni non valido')
    return json.loads(path.read_text()) if path.exists() else {}


def dismiss(root, source_ids, reason):
    """Evaluate individual sources as not worth a reusable lesson; retain evidence."""
    from .experience import entries as observations, locked
    if not isinstance(source_ids, list) or not 1 <= len(source_ids) <= 6 or any(not isinstance(s, str) or not ID.fullmatch(s) for s in source_ids):
        raise ValueError('Valuta da una a sei fonti alla volta')
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 1000 or redact_memory(reason) != reason:
        raise ValueError('Indica perché queste fonti non richiedono una lezione')
    with locked(root) as folder:
        known = {r['id'] for r in observations(folder)}
        if any(s not in known for s in source_ids):
            raise ValueError('Fonte non trovata')
        decisions = reviewed(folder)
        for source in source_ids:
            decisions[source] = {'decision': 'not_generalized', 'reason': reason.strip(), 'at': utcnow()}
        atomic_json(folder / 'lesson-decisions.json', decisions)


def accepted(root):
    path = Path(root) / 'accepted-lessons.json'
    if path.is_symlink():
        raise ValueError('Indice accettazioni non valido')
    manual = set(json.loads(path.read_text())) if path.exists() else set()
    return manual | automatic(root)


def category(record, sources):
    lesson = record['basis']['lesson']
    if 'category' in lesson:
        return lesson['category']
    # Legacy worker findings were explicitly captured as tool-use notes. Never
    # classify arbitrary coordinator lessons from keywords or the chosen app.
    evidence = [sources.get(s, {}) for s in record['basis']['source_ids']]
    if lesson.get('tools') and evidence and all(
            s.get('kind') == 'sandbox_tool_use' and s.get('suggested_lesson') == lesson for s in evidence):
        return 'tool_operation'
    return 'production_method'


def automatic(root):
    from .experience import entries as observations, disabled
    sources = {r['id']: r['observation'] for r in observations(root)}
    excluded = disabled(root)
    result = set()
    for record in entries(root):
        basis = record['basis']
        if (category(record, sources) != 'tool_operation' or record['id'] in excluded
                or set(basis['source_ids']) & excluded or not basis.get('tool_versions')
                or any(v in ('unknown', '', None) for v in basis['tool_versions'].values())):
            continue
        if all(sources.get(s, {}).get('technical_validation', {}).get('status') == 'passed'
               and sources[s].get('suggested_lesson') == basis['lesson'] for s in basis['source_ids']):
            result.add(record['id'])
    return result


def accept(root, identifier, enabled=True):
    """Owner-only API action; the coordinator can propose, never approve itself."""
    from .experience import locked
    if not isinstance(identifier, str) or not ID.fullmatch(identifier) or type(enabled) is not bool:
        raise ValueError('Accettazione non valida')
    with locked(root) as folder:
        record = next((r for r in entries(folder) if r['id'] == identifier), None)
        if record is None:
            raise ValueError('Lezione proposta non trovata')
        manual_path = folder / 'accepted-lessons.json'
        if manual_path.is_symlink():
            raise ValueError('Indice accettazioni non valido')
        ids = set(json.loads(manual_path.read_text())) if manual_path.exists() else set()
        ids.add(identifier) if enabled else ids.discard(identifier)
        atomic_json(folder / 'accepted-lessons.json', sorted(ids))
        # Disabling automatic knowledge is persistent and survives recollection.
        from .experience import disabled, entries as observations
        exclusions = disabled(folder)
        sources = {r['id']: r['observation'] for r in observations(folder)}
        if enabled or category(record, sources) != 'tool_operation':
            exclusions.discard(identifier)
        else:
            exclusions.add(identifier)
        atomic_json(folder / 'excluded.json', sorted(exclusions))
