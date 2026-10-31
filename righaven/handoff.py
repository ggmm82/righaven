"""Validate specialist deliverables before reporting a successful run."""
import json
from pathlib import Path
import re
import zipfile


POLICY_CHECK = re.compile(r'[a-z][a-z0-9_]{0,39}\.[a-z][a-z0-9_]{0,59}\Z')

DELIVERY_SCHEMA = {
    'type': 'object', 'properties': {
        'source_status': {'type': 'string', 'enum': ['included', 'unavailable', 'not_applicable']},
        'source_note': {'type': 'string', 'minLength': 1},
        'files': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'object', 'properties': {
                'path': {'type': 'string'},
                'primary': {'type': 'boolean'},
                'role': {'type': 'string', 'enum': ['editable_source', 'source_archive', 'export', 'dependency', 'preview', 'report']},
                'format': {'type': 'string', 'minLength': 1},
                'open_with': {'type': 'string', 'minLength': 1},
                'editability': {'type': 'string', 'minLength': 1},
                'reopen': {'type': 'object', 'properties': {
                    'status': {'type': 'string', 'enum': ['passed', 'failed', 'not_run']},
                    'evidence': {'type': 'string', 'minLength': 1}},
                    'required': ['status', 'evidence'], 'additionalProperties': False},
                'limitations': {'type': 'array', 'items': {'type': 'string', 'minLength': 1}}},
            'required': ['path', 'role', 'format', 'open_with', 'editability', 'reopen', 'limitations'],
            'additionalProperties': False}}},
    'required': ['source_status', 'source_note', 'files'], 'additionalProperties': False}

SOURCE_REF = {'type':'object','properties':{'path':{'type':'string'},'member':{'type':'string'}},
              'required':['path'],'additionalProperties':False}
DELIVERY_SCHEMA['properties']['components'] = {'type':'array','minItems':1,'maxItems':12,'items':{
    'type':'object','properties':{'name':{'type':'string','minLength':1,'maxLength':140},'tool':{'type':'string','minLength':1,'maxLength':48},
        'artifacts':{'type':'array','minItems':1,'maxItems':64,'items':SOURCE_REF},
        'sources':{'type':'array','minItems':1,'maxItems':24,'items':SOURCE_REF},
        'provided_inputs':{'type':'array','maxItems':64,'items':{'type':'string'}}},
    'required':['name','tool','artifacts','sources'],'additionalProperties':False}}
DELIVERY_SCHEMA['properties']['timing'] = {'type':'object','properties':{
    'master':{'type':'string'},'cues':{'type':'array','minItems':1,'maxItems':12,'items':{
        'type':'object','properties':{'name':{'type':'string'},'visual_seconds':{'type':'number'},
            'tolerance_seconds':{'type':'number','minimum':.01,'maximum':.25}},
        'required':['name','visual_seconds'],'additionalProperties':False}}},
    'required':['master','cues'],'additionalProperties':False}


HANDOFF_SCHEMA = {'type': 'object', 'properties': {
        'task': {'type': 'string'},
        'delivery': DELIVERY_SCHEMA,
        'source_files': {'type': 'array', 'items': {'type': 'string'}},
        'output_files': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}},
        'previews': {'type': 'array', 'items': {'type': 'string'}},
        'checks': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'properties': {
            'name': {'type': 'string'}, 'status': {'type': 'string', 'enum': ['passed', 'failed', 'not_run']},
            'evidence': {'type': 'string'}, 'scope': {'type':'string','enum':['current','historical','environment']},
            'superseded_by': {'type':'string','minLength':1},
            'policy_check': {'type':'string','pattern':'^[a-z][a-z0-9_]{0,39}\\.[a-z][a-z0-9_]{0,59}$'}},
            'required': ['name', 'status', 'evidence'], 'additionalProperties': False}},
        'warnings': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['task', 'source_files', 'output_files', 'previews', 'checks', 'warnings', 'delivery'],
        'additionalProperties': False}

def validate_delivery(value):
    """Validate claims and downloadable sources, not actual application compatibility."""
    delivery = value.get('delivery')
    if not isinstance(delivery, dict) or delivery.get('source_status') not in ('included', 'unavailable', 'not_applicable'):
        raise ValueError('handoff.json: delivery e source_status obbligatori')
    if not isinstance(delivery.get('source_note'), str) or not delivery['source_note'].strip():
        raise ValueError('handoff.json: source_note deve spiegare sorgenti e limiti')
    files = delivery.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('handoff.json: delivery.files obbligatorio')
    if sum(item.get('primary') is True for item in files if isinstance(item,dict)) > 1:
        raise ValueError('handoff.json: seleziona un solo prodotto primario')
    outputs = set(value['output_files'])
    allowed = outputs | set(value.get('previews', []))
    seen, sources, unverified = set(), [], False
    for item in files:
        if not isinstance(item, dict):
            raise ValueError('handoff.json: metadati file non validi')
        path = item.get('path')
        if not isinstance(path, str) or path not in allowed or path in seen:
            raise ValueError('handoff.json: delivery.path deve essere unico e già elencato negli output o anteprime')
        seen.add(path)
        if 'primary' in item and (type(item['primary']) is not bool or item['primary'] and item.get('role') not in ('export','editable_source','source_archive')):
            raise ValueError('handoff.json: primary deve identificare un prodotto o un sorgente scaricabile')
        if item.get('role') not in ('editable_source', 'source_archive', 'export', 'dependency', 'preview', 'report'):
            raise ValueError('handoff.json: ruolo di consegna non valido')
        for field in ('format', 'open_with', 'editability'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f'handoff.json: delivery.files richiede {field}')
        reopen = item.get('reopen')
        if (not isinstance(reopen, dict) or reopen.get('status') not in ('passed', 'failed', 'not_run')
                or not isinstance(reopen.get('evidence'), str) or not reopen['evidence'].strip()):
            raise ValueError('handoff.json: riapertura richiede status ed evidence')
        limitations = item.get('limitations')
        if not isinstance(limitations, list) or not all(isinstance(s, str) and s.strip() for s in limitations):
            raise ValueError('handoff.json: limitations deve essere una lista di stringhe')
        if reopen['status'] != 'passed':
            unverified = True
            if not limitations:
                if reopen['status'] == 'not_run' and item['role'] in ('dependency', 'report'):
                    # A missing repetition of an auxiliary check must not discard
                    # an otherwise usable job. Keep not_run, add the truthful
                    # limit and warning; never promote an unverified source.
                    note = 'Riapertura non eseguita per ' + Path(path).name + ': ' + reopen['evidence']
                    item['limitations'] = [note]
                    if note not in value['warnings']:
                        value['warnings'].append(note)
                else:
                    raise ValueError('handoff.json: riapertura non verificata richiede un limite esplicito')
        if item['role'] in ('editable_source', 'source_archive'):
            if path not in outputs:
                raise ValueError('handoff.json: il sorgente modificabile deve essere scaricabile in output_files')
            sources.append(item)
    if outputs - seen:
        raise ValueError('handoff.json: mancano metadati di consegna per alcuni output')
    status = delivery['source_status']
    if (status == 'included') != bool(sources):
        raise ValueError('handoff.json: source_status non corrisponde ai sorgenti consegnati')
    if status == 'not_applicable' and (not any(item['role'] == 'report' for item in files)
            or any(item['role'] not in ('report', 'preview', 'dependency') for item in files)):
        raise ValueError('handoff.json: un prodotto esportato richiede sorgenti o indisponibilità dichiarata')
    if (status == 'unavailable' or unverified) and not any(w.strip() for w in value['warnings']):
        raise ValueError('handoff.json: sorgenti mancanti o riapertura non verificata richiedono warnings')


def duplicate_outputs(paths, output_dir):
    """Groups of delivered files with identical content, as paths relative to the output folder."""
    import hashlib
    groups = {}
    for filename in paths:
        path = Path(filename)
        if not path.is_file() or path.is_symlink():
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                digest.update(chunk)
        name = str(path.resolve().relative_to(output_dir)) if path.resolve().is_relative_to(output_dir) else str(path)
        groups.setdefault(digest.hexdigest(), []).append(name)
    return [sorted(group) for group in groups.values() if len(group) > 1]


def validate_handoff(output_dir, workspace, *, require_delivery=False):
    output_dir, workspace = Path(output_dir).resolve(), Path(workspace).resolve()
    manifest = output_dir / 'handoff.json'
    if not manifest.resolve().is_relative_to(output_dir):
        raise ValueError('handoff.json esterno alla cartella assegnata')
    value = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not isinstance(value.get('task'), str) or not value['task'].strip():
        raise ValueError('handoff.json: task obbligatorio')
    # Model-authored bookkeeping is retained in work/, never advertised as a
    # creative output. Normalize only known report files; sources and arbitrary
    # work files still go through all the original checks below.
    delivery = value.get('delivery')
    if isinstance(delivery, dict) and isinstance(delivery.get('files'), list) and isinstance(value.get('output_files'), list):
        bookkeeping = {str(output_dir / 'work' / name) for name in
                       ('method.json', 'checkpoint.json', 'tool-events.json', 'tool-lessons.json')}
        removed = {item.get('path') for item in delivery['files'] if isinstance(item, dict)
                   and item.get('role') == 'report' and isinstance(item.get('path'), str) and item['path'] in bookkeeping
                   and not Path(item['path']).is_symlink() and Path(item['path']).is_file()
                   and Path(item['path']).resolve().is_relative_to(output_dir)}
        if removed:
            value['output_files'] = [p for p in value['output_files'] if not isinstance(p, str) or p not in removed]
            delivery['files'] = [item for item in delivery['files'] if not isinstance(item, dict)
                                 or not isinstance(item.get('path'), str) or item['path'] not in removed]
            value['normalization'] = {'technical_reports_retained': sorted(removed)}
            if isinstance(value.get('warnings'), list):
                value['warnings'].append('Registri tecnici conservati in work/ e separati dai prodotti consegnati.')
    for field in ('source_files', 'output_files', 'previews'):
        paths = value.get(field, [] if field == 'previews' else None)
        if not isinstance(paths, list) or (field == 'output_files' and not paths):
            raise ValueError(f'handoff.json: {field} deve essere una lista di file')
        if field == 'output_files' and len(paths) > 40:
            raise ValueError('handoff.json: raggruppa risorse e sorgenti in pacchetti; massimo 40 download per consegna')
        for filename in paths:
            if not isinstance(filename, str):
                raise ValueError(f'handoff.json: percorso non valido in {field}')
            path = Path(filename)
            boundary = workspace if field == 'source_files' else output_dir
            if not path.is_absolute() or not path.resolve().is_relative_to(boundary):
                raise ValueError(f'handoff.json: percorso esterno in {field}')
            if not path.is_file() or (field != 'source_files' and path.stat().st_size == 0):
                raise ValueError(f'handoff.json: file mancante o vuoto in {field}')
            if field == 'output_files' and path.resolve().is_relative_to(output_dir / 'work'):
                raise ValueError('handoff.json: i file tecnici in work/ non sono prodotti finali')
    duplicates = duplicate_outputs(value['output_files'], output_dir)
    if duplicates and isinstance(value.get('warnings'), list):
        note = ('File identici consegnati più volte; tieni una sola copia (per esempio in assets/ accanto al sorgente): '
                + '; '.join(' = '.join(group) for group in duplicates[:5]))
        if note not in value['warnings']:
            value['warnings'].append(note)
        value['duplicate_outputs'] = duplicates
    checks = value.get('checks')
    if not isinstance(checks, list) or not checks:
        raise ValueError('handoff.json: checks obbligatori')
    for check in checks:
        if (not isinstance(check, dict) or check.get('status') not in ('passed', 'failed', 'not_run')
                or not isinstance(check.get('name'), str) or not check['name'].strip()
                or not isinstance(check.get('evidence'), str) or not check['evidence'].strip()):
            raise ValueError('handoff.json: check richiede name, status e evidence')
        if check.get('scope', 'current') not in ('current', 'historical', 'environment'):
            raise ValueError('handoff.json: check.scope deve essere current, historical o environment')
        if 'policy_check' in check and (not isinstance(check['policy_check'], str)
                or not POLICY_CHECK.fullmatch(check['policy_check'])):
            raise ValueError('handoff.json: policy_check usa la forma sheet.controllo del Policy Plan')
        replacement = check.get('superseded_by')
        if check.get('scope') == 'historical':
            matches = [c for c in checks if isinstance(c, dict) and c.get('name') == replacement
                       and c.get('scope', 'current') == 'current' and c.get('status') == 'passed']
            if not isinstance(replacement, str) or not replacement.strip() or len(matches) != 1 or replacement == check['name']:
                raise ValueError('handoff.json: un check historical richiede superseded_by con il nome univoco di un controllo current passed realmente eseguito')
        elif replacement is not None:
            raise ValueError('handoff.json: superseded_by ammesso soltanto per un controllo historical')
    if not isinstance(value.get('warnings'), list) or not all(isinstance(w, str) for w in value['warnings']):
        raise ValueError('handoff.json: warnings deve essere una lista di stringhe')
    if require_delivery or 'delivery' in value:
        validate_delivery(value)
        if value['delivery'].get('components') is not None:
            try:
                from .component_sources import inspect_components
            except ImportError:
                from component_sources import inspect_components
            try:
                coverage = inspect_components(value, value['delivery']['files'], workspace=workspace, inventory_only=True)
            except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, RuntimeError, NotImplementedError) as error:
                raise ValueError('handoff.json: archivio dei sorgenti non leggibile: ' + str(error)[:500]) from error
            if coverage['issues']:
                raise ValueError('handoff.json: ' + '; '.join(coverage['issues'][:8]))
    report = output_dir / 'quality-review.json'
    if str(report) in value['output_files'] and report.is_file():
        if report.stat().st_size > 30000:
            raise ValueError('Revisione: rapporto troppo grande')
        review = json.loads(report.read_text())
        if isinstance(review, dict) and (review.get('review_version') == 2 or 'findings' in review):
            try:
                from .revision import findings
            except ImportError:
                from revision import findings
            criteria = review.get('criteria', [])
            if not isinstance(criteria, list) or any(not isinstance(c, dict) or c.get('status') not in
                    ('passed', 'failed', 'not_run') for c in criteria):
                raise ValueError('Revisione: criteri non validi')
            findings(review, criteria)
    return value


def blocking_checks(checks):
    """Historical failures retain their outcome; only a validated successor retires them."""
    for check in checks:
        if check.get('status') != 'failed':
            continue
        if check.get('scope') == 'environment':
            continue
        replacements = [c for c in checks if c.get('name') == check.get('superseded_by')
                        and c.get('scope', 'current') == 'current' and c.get('status') == 'passed']
        if check.get('scope') != 'historical' or len(replacements) != 1 or check.get('superseded_by') == check.get('name'):
            yield check


def product_files(files):
    """A product may also be its editable source; reports never become products."""
    eligible = [item for item in files if item.get('role') in ('export','editable_source','source_archive') and item.get('primary') is not False]
    explicit = [item for item in eligible if item.get('primary') is True]
    if explicit:
        return explicit
    exports = [item for item in eligible if item.get('role') == 'export']
    if exports:
        return exports
    editable = [item for item in eligible if item.get('role') == 'editable_source']
    return editable if len(editable) == 1 else []


def main():
    """Give every CLI worker the same preflight feedback as submit_handoff."""
    import argparse
    parser = argparse.ArgumentParser(description='Controlla i metadati senza approvare il prodotto o modificare i file.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('schema')
    check = sub.add_parser('validate')
    check.add_argument('output_dir', type=Path)
    check.add_argument('--workspace', type=Path, default=Path('/mnt/user-data'))
    args = parser.parse_args()
    if args.command == 'schema':
        print(json.dumps(HANDOFF_SCHEMA, ensure_ascii=False))
        return 0
    try:
        handoff = validate_handoff(args.output_dir, args.workspace, require_delivery=True)
    except (ValueError, OSError) as error:
        print(json.dumps({'ok': False, 'product_approved': False, 'error': str(error),
            'instruction': 'Correggi soltanto il manifest usando i file esistenti. Conserva failed e not_run, esplicita i limiti; non rigenerare il prodotto per un errore di metadati.'}, ensure_ascii=False))
        return 1
    print(json.dumps({'ok': True, 'product_approved': False, 'output_count': len(handoff['output_files']),
        'failed_checks': [c['name'] for c in blocking_checks(handoff['checks'])],
        'historical_checks': [c for c in handoff['checks'] if c.get('scope') == 'historical'],
        'instruction': 'Manifest strutturalmente valido; compatibilità, qualità e contratto finale richiedono le rispettive verifiche.'}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
