"""Version-bound project instructions from retained records, never a new LLM run."""
import hashlib
from .handoff import product_files
import json
from pathlib import Path
import tempfile
import zipfile

from .progress import clean_summary
from .project_skills import redact_memory

MAX_BUNDLE = 4 * 1024 ** 3
PURPOSES = {'preview': 'Campione', 'delivery': 'Consegna', 'review': 'Revisione', 'work': 'Lavorazione'}


def text(value, limit=1500):
    return clean_summary(redact_memory(value), limit) if isinstance(value, str) else ''


def strings(value, limit=8):
    return [text(v) for v in value[:limit] if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def document(workspace, folder, name):
    from .projects import artifact_path, public_artifact
    path = artifact_path(workspace, folder / 'work' / name) if folder else None
    if not path or path.stat().st_size > 24000:
        return {}, None
    try:
        data = json.loads(path.read_text())
        return (data, public_artifact(workspace, path)) if isinstance(data, dict) else ({}, None)
    except (ValueError, OSError):
        return {}, None


def build(workspace, delivery_id=None):
    from .projects import locked, load, artifact_path, public_artifact, workspace_path
    with locked(workspace) as folder:
        project = load(folder, workspace)
    if not project:
        raise ValueError('Nessun progetto registrato')
    attempts = [(s, a) for s in project['steps'] for a in s['attempts']]
    attempts.sort(key=lambda pair: (pair[1].get('started_at', ''), pair[1].get('finished_at', '')))
    def identifier(pair):
        step, attempt = pair
        return (attempt.get('delivery_record') or {}).get('id') or Path(attempt.get('output_dir', '')).name or step['id']
    candidates = [(s, a) for s, a in attempts if (a.get('delivery_record') or {}).get('files')
                  and a.get('context', {}).get('purpose') != 'review']
    selected = next((pair for pair in reversed(candidates) if identifier(pair) == delivery_id), None) if delivery_id else next(
        (pair for pair in reversed(candidates) if project.get('product_path') in pair[1].get('output_files', [])),
        candidates[-1] if candidates else None)
    if not selected:
        raise ValueError('La consegna richiesta non ha ancora una guida disponibile')
    step, attempt = selected
    selected_id = identifier(selected)
    record = attempt['delivery_record']
    directory = workspace_path(workspace, attempt.get('output_dir', ''))
    directory = directory.resolve() if directory else None
    files, seen, unavailable = [], set(), []
    for item in record.get('files', [])[:40]:
        path = artifact_path(workspace, item.get('path', ''))
        path = path.resolve() if path else None
        if not path or not public_artifact(workspace, path).startswith('/mnt/user-data/outputs/'):
            unavailable.append(text(Path(str(item.get('path', ''))).name))
            continue
        public = public_artifact(workspace, path)
        if public in seen:
            continue
        seen.add(public)
        relative = path.relative_to(directory).as_posix() if directory and path.is_relative_to(directory) else public.removeprefix('/mnt/user-data/outputs/')
        files.append({'path': public, 'name': text(relative), 'role': text(item.get('role')), 'primary':item.get('primary'),
            'open_with': text(item.get('open_with')), 'editability': text(item.get('editability')),
            'limitations': strings(item.get('limitations')), 'sha256': item.get('sha256', ''),
            'bundle_path': 'File/' + relative, 'size_bytes': path.stat().st_size})
    if not files:
        raise ValueError('I file di questa consegna non sono più disponibili')
    import re
    documents = []
    for f in files:
        if len(documents) == 4:
            break
        name = Path(f['name']).name
        if Path(name).suffix.lower() not in ('.md', '.txt') or not re.search(r'readme|leggimi|ricetta|guida|manual|instructions|getting.started', name, re.I):
            continue
        path = artifact_path(workspace, f['path'])
        if path and path.stat().st_size <= 48000:
            documents.append({'name': f['name'], 'path': f['path'], 'text': text(path.read_text(errors='replace'), 12000)})
    method, method_path = document(workspace, directory, 'method.json')
    notes, notes_path = document(workspace, directory, 'guide.json')
    edit = []
    for item in (notes.get('editing') if isinstance(notes.get('editing'), list) else [])[:8]:
        if not isinstance(item, dict) or not isinstance(item.get('files'), list):
            continue
        linked = []
        for name in item['files'][:12]:
            if not isinstance(name, str):
                continue
            linked += [f['path'] for f in files if name in (f['path'], f['name'])]
        steps = strings(item.get('steps'))
        if linked and steps and text(item.get('goal')):
            edit.append({'goal': text(item['goal']), 'files': sorted(set(linked)), 'steps': steps,
                         'check': text(item.get('check'))})
    team, history, methods, previous_exports = [], [], [], None
    method_attempts = attempts if len(attempts) <= 20 else attempts[:5] + attempts[-15:]
    if selected not in method_attempts:
        method_attempts.append(selected)
    for activity, run in attempts:
        role = text(run.get('role_title') or activity.get('role_id') or activity['agent'])
        if not any(t['title'] == role for t in team):
            team.append({'title': role, 'goal': text(activity['goal'])})
        purpose = run.get('context', {}).get('purpose', 'work')
        if (activity, run) in method_attempts:
            source, source_path = document(workspace, workspace_path(workspace, run.get('output_dir', '')), 'method.json')
            if text(source.get('approach')):
                methods.append({'id': identifier((activity, run)), 'title': text(activity['goal']),
                    'actor': role, 'kind': PURPOSES.get(purpose, 'Lavorazione'),
                    'selected': run is attempt, 'approach': text(source['approach']),
                    'steps': strings(source.get('steps'), 12), 'path': source_path})
        delivery = run.get('delivery_record') or {}
        exports = tuple(sorted(f.get('sha256', '') for f in product_files(delivery.get('files', []))
                               if f.get('sha256')))
        change = 'not_recorded'
        if exports and purpose != 'review':
            change = 'identical_export' if exports == previous_exports else 'different_export'
            if previous_exports is None:
                change = 'first_export'
            previous_exports = exports
        report = run.get('quality_review') or {}
        history.append({'id': identifier((activity, run)), 'title': text(activity['goal']), 'actor': role,
            'kind': PURPOSES.get(purpose, 'Lavorazione'), 'status': text(run.get('status')),
            'started_at': run.get('started_at', ''), 'finished_at': run.get('finished_at', ''),
            'runtime_image': text(run.get('runtime_image')),
            'change': change, 'review_status': text(report.get('status')),
            'detail': text(run.get('error') or '; '.join(strings(run.get('failed_checks'))), 700)})
    coverage = record.get('source_coverage') or {}
    versions = {}
    if isinstance(attempt.get('tool_environment'), dict):
        try:
            from .project_skills import read_document
            versions = json.loads(read_document(workspace, attempt['tool_environment']))
            versions = versions if isinstance(versions, dict) else {}
        except (OSError, ValueError, KeyError):
            pass
    components = [{'name': text(c.get('name')), 'tool': text(c.get('tool')),
                   'version': text(versions.get(c.get('tool'))), 'status': text(c.get('status'))}
                  for c in coverage.get('components', [])[:12] if isinstance(c, dict)]
    reports = []
    export_hashes = {f['sha256'] for f in product_files(files) if f['sha256']}
    source_hashes = {f['sha256'] for f in files if f['role'] in ('editable_source', 'source_archive') and f['sha256']}
    for _, run in attempts:
        review = run.get('quality_review') or {}
        if review.get('sha256') in export_hashes:
            reports.append({'status': text(review.get('status')),
                'matches_current_brief': review.get('contract_hash') == (project.get('acceptance') or {}).get('hash'),
                'matches_sources': not source_hashes or bool(review.get('input_hashes'))
                    and source_hashes <= set(review['input_hashes'].values()),
                'criteria': [{'criterion': text(c.get('criterion')), 'status': text(c.get('status')),
                    'method': text(c.get('method')), 'evidence': text(c.get('evidence')), 'scope': c.get('scope','requirement')}
                    for c in review.get('criteria', [])[:24]],
                'path': public_artifact(workspace, review.get('report_path', ''))})
    omitted = max(0, len(history) - 60)
    if omitted:
        history = history[:5] + history[-55:]
    purpose=attempt.get('context',{}).get('purpose','work')
    exports=[f['path'] for f in product_files(files)]
    primary=project.get('product_path') if project.get('product_path') in exports else next(iter(exports),None)
    package_status=record.get('source_package_status','not_verified')
    return {'schema_version': 1, 'project_id': project['id'], 'delivery_id': selected_id,
        'delivery': {'purpose':purpose,'label':PURPOSES.get(purpose,'Lavorazione'),
            'primary_path':primary,'source_package_status':package_status,
            'pending':strings(record.get('issues'))+strings(record.get('finalization_pending')),
            'bundle_note':'Questo ZIP raccoglie file e guida della stessa lavorazione. Non modifica i sorgenti e non dimostra che i progetti nativi siano portabili.'},
        'title': text(attempt.get('project_title') or record.get('title') or step['goal'], 400),
        'result': text(record.get('title') or step['goal']),
        'brief': text(attempt.get('project_brief') or attempt.get('task') or record.get('title') or step['goal'], 4000),
        'is_current': project.get('product_path') in attempt.get('output_files', []),
        'technical_status': text(record.get('technical_status', 'not_verified')),
        'snapshot_at': project.get('updated_at', ''), 'files': files, 'documents': documents, 'team': team[:64],
        'method': {'approach': text(method.get('approach')), 'steps': strings(method.get('steps'), 12),
            'scripts': strings(method.get('scripts')), 'limits': strings(method.get('limits')), 'path': method_path},
        'instructions': {'overview': text(notes.get('overview')), 'use': strings(notes.get('use')),
                         'editing': edit, 'limits': strings(notes.get('limits')), 'path': notes_path},
        'components': components, 'methods': methods, 'methods_omitted': max(0, len(attempts) - len(method_attempts)),
        'reviews': reports[-4:], 'history': history, 'history_omitted': omitted,
        'unavailable_files': unavailable,
        'limitations': strings(record.get('issues')) + strings(record.get('finalization_pending'))
            + ['File registrato non disponibile: ' + name for name in unavailable]}


def markdown(guide, *, bundled=False):
    # Escape narrative as text; only runtime-owned file references become links.
    import re
    def prose(value):
        return re.sub(r'([\\`*_{}\[\]<>#!|])', r'\\\1', str(value)).replace('\r', '')
    lines = ['# Guida del progetto', '', prose(guide['title']), '', '## Il risultato', '',
        prose(guide['result']), '', 'Consegna: ' + guide['delivery_id'],
        'Fotografia del progetto: ' + guide['snapshot_at'],
        'Controlli tecnici: ' + guide['technical_status'], '', prose(guide['brief']), '',
        '## Come è stato fatto', '', prose(guide['method']['approach']) or 'Metodo non registrato.', '']
    lines += [f'{i}. {prose(s)}' for i, s in enumerate(guide['method']['steps'], 1)]
    lines += ['', '### Procedure delle lavorazioni conservate', '', 'Ogni procedura resta legata alla propria lavorazione.', '']
    for method in guide['methods']:
        lines += ['- **' + prose(method['kind'] + ': ' + method['title']) + '** · ' + prose(method['actor']),
                  '  - ' + prose(method['approach'])]
        lines += ['  - ' + prose(s) for s in method['steps']]
    if guide['methods_omitted']:
        lines += ['Procedure intermedie non incluse nella sintesi: ' + str(guide['methods_omitted'])]
    lines += ['', 'Metodo e istruzioni sono dichiarazioni della squadra conservate nei file di lavoro; le verifiche sono riportate separatamente.',
              '', '## La squadra', '']
    lines += ['- ' + prose(t['title']) + ': ' + prose(t['goal']) for t in guide['team']]
    lines += ['', '## Componenti e strumenti associati', '']
    lines += ['- ' + prose(c['name']) + ': ' + prose(c['tool']) + ' ' + prose(c['version']) + ' · ' + c['status'] for c in guide['components']]
    if not guide['components']:
        lines.append('Associazioni fra componenti e strumenti non registrate.')
    lines += ['', '## Usare e modificare il risultato', '', prose(guide['instructions']['overview'])]
    lines += [f'{i}. {prose(s)}' for i, s in enumerate(guide['instructions']['use'], 1)]
    for item in guide['instructions']['editing']:
        lines += ['', '### ' + prose(item['goal']), '', 'File: ' + ', '.join(prose(p) for p in item['files'])]
        lines += [f'{i}. {prose(s)}' for i, s in enumerate(item['steps'], 1)]
        if item['check']:
            lines += ['Controllo dopo la modifica: ' + prose(item['check'])]
    if not guide['instructions']['editing']:
        lines += ['', 'Procedure di modifica dettagliate non registrate. La mappa seguente conserva le indicazioni disponibili; consulta anche le istruzioni originali incluse.']
    for doc in guide['documents']:
        fence = '`' * max(3, 1 + max((len(m[0]) for m in re.finditer(r'`+', doc['text'])), default=0))
        lines += ['', '### Istruzioni originali: ' + prose(doc['name']), '', fence + 'text', doc['text'], fence]
    lines += ['', '## Mappa dei file', '']
    from urllib.parse import quote
    for f in guide['files']:
        name = prose(f['name'])
        label = '[' + name + '](' + quote(f['bundle_path'], safe='/') + ')' if bundled else name
        lines += ['- **' + label + '** · ' + prose(f['role']), '  - Apertura: ' + (prose(f['open_with']) or 'Non registrata'),
                  '  - Modifiche: ' + (prose(f['editability']) or 'Non registrate')]
    lines += ['', '## Storia delle lavorazioni', '', 'Orari ISO in UTC. La storia comprende altre consegne e possibili release della conversazione: non tutti i passaggi hanno contribuito a questa versione. Byte diversi non dimostrano un miglioramento creativo.', '']
    for entry in guide['history']:
        change = {'identical_export': ' · export identico al precedente', 'different_export': ' · export con byte diversi',
                  'first_export': ' · primo export registrato'}.get(entry['change'], '')
        lines += ['- ' + entry['started_at'] + ' — ' + prose(entry['kind'] + ': ' + entry['title']) +
                  ' · ' + prose(entry['actor']) + ' · ' + entry['status'] + change]
        if entry.get('runtime_image'):
            lines += ['  - Immagine sandbox configurata: ' + prose(entry['runtime_image'])]
        if entry['detail']:
            lines += ['  - ' + prose(entry['detail'])]
    if guide['history_omitted']:
        lines.append('Passaggi intermedi non inclusi nella sintesi: ' + str(guide['history_omitted']))
    lines += ['', 'La storia usa gli incarichi ancora conservati nel progetto; non ricostruisce eventi eliminati.',
              '', '## Verifiche e limiti', '']
    for review in guide['reviews']:
        lines += ['Revisione registrata sugli hash dell’export: ' + review['status'] +
                  (' · contratto corrente' if review['matches_current_brief'] else ' · contratto precedente') +
                  (' · sorgenti associati agli input della revisione' if review['matches_sources'] else ' · associazione ai sorgenti non confermata')]
        lines += ['- ' + c['status'] + (' · controllo aggiuntivo' if c.get('scope') == 'supplementary' else '') + ' · ' + prose(c['criterion']) + ': ' + prose(c['evidence']) for c in review['criteria']]
    if not guide['reviews']:
        lines.append('Nessuna revisione associata agli hash registrati di questa consegna.')
    limits = guide['limitations'] + guide['method']['limits'] + guide['instructions']['limits']
    limits += [v for f in guide['files'] for v in f['limitations']]
    lines += ['- ' + prose(s) for s in dict.fromkeys(limits)]
    lines += ['', 'La guida documenta il progetto; non è una nuova verifica, una lezione approvata o una certificazione del risultato.', '']
    return '\n'.join(lines)


def entrypoint(guide):
    """Runtime-owned navigation; an outer ZIP never upgrades source portability."""
    from urllib.parse import quote
    import re
    def prose(value):return re.sub(r'([\\`*_{}\[\]<>#!|])', r'\\\1', str(value)).replace('\r','')
    info=guide.get('delivery',{})
    lines=['# Da dove iniziare', '', info.get('label','Lavorazione')+' · '+guide['delivery_id'], '',
           'Questi file appartengono soltanto a questa lavorazione.',
           'Campioni e contributi possono coprire solo una parte del risultato richiesto.', '',
           '## Risultati da aprire', '']
    for f in guide['files']:
        if f['role']=='export':
            lines.append('- ['+prose(f['name'])+']('+quote(f['bundle_path'],safe='/')+') · '+prose(f['open_with'] or 'App non indicata'))
    lines+=['', '## Modificare i sorgenti', '',
            'Pacchetto sorgenti: '+{'verified':'verificato dal runtime', 'not_packaged':'non confezionato',
                'incomplete':'da completare', 'not_applicable':'non previsto per questa lavorazione'}.get(info.get('source_package_status'),'verifica non registrata'),
            'Gli archivi sorgenti originali restano nella cartella File. Estrarli interamente e seguire le loro istruzioni.',
            'La presenza di un progetto nativo isolato non garantisce che contenga tutte le risorse.', '',
            '## Istruzioni e verifiche', '', '[Apri la guida del progetto](GUIDA-PROGETTO.md)',
            'La guida elenca app, file modificabili, metodo, storia e limiti. Il manifest associa ogni file al suo hash.', '']
    if info.get('pending'):lines+=['## Da completare', '', *['- '+prose(s) for s in info['pending']], '']
    return '\n'.join(lines)


def bundle(workspace, guide):
    """Outer package only: original bytes and reviewed archive hashes stay intact."""
    from .projects import artifact_path
    if guide['unavailable_files']:
        raise ValueError('Alcuni file registrati non sono disponibili: scarica separatamente quelli conservati')
    if sum(f['size_bytes'] for f in guide['files']) > MAX_BUNDLE:
        raise ValueError('Consegna oltre 4 GiB: scarica guida e file originali separatamente')
    stream = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    manifest = []
    try:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('LEGGIMI.md', entrypoint(guide))
            archive.writestr('GUIDA-PROGETTO.md', markdown(guide, bundled=True))
            archive.writestr('guida-progetto.json', json.dumps(guide, ensure_ascii=False, indent=2))
            for f in guide['files']:
                path = artifact_path(workspace, f['path'])
                if not path:
                    raise ValueError('Un file della consegna non è più disponibile')
                sha, count = hashlib.sha256(), 0
                import os
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as source:
                    if not Path('/proc/self/fd/' + str(source.fileno())).resolve().is_relative_to(Path(workspace).resolve()):
                        raise ValueError('File esterno alla conversazione')
                    with archive.open(f['bundle_path'], 'w', force_zip64=True) as target:
                        while chunk := source.read(1024 * 1024):
                            sha.update(chunk); count += len(chunk)
                            if count > f['size_bytes']:
                                raise ValueError('File modificato durante il download: aggiorna la consegna')
                            target.write(chunk)
                if count != f['size_bytes'] or f['sha256'] and sha.hexdigest() != f['sha256']:
                    raise ValueError('File diverso dalla consegna registrata: aggiorna la guida')
                manifest.append({'path': f['bundle_path'], 'sha256': sha.hexdigest(), 'original_path': f['path']})
            archive.writestr('manifest-consegna.json', json.dumps({'delivery_id': guide['delivery_id'], 'delivery':guide.get('delivery',{}), 'files': manifest}, indent=2))
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise
