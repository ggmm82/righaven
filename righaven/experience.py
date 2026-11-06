"""User-private, evidence-bound observations, never automatic edits to shared skills."""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re

from .acceptance import fingerprint
from .progress import utcnow
from .project_skills import redact_memory, scoped_file, read_document, ROLE_ID
from .source_packages import digest
from .state import atomic_json

ID = re.compile(r'[a-f0-9]{64}\Z')


def entries(root):
    root = Path(root)
    if not root.exists():
        return []
    if root.is_symlink():
        raise ValueError('Archivio esperienza non valido')
    result = []
    for path in root.glob('*.json'):
        if not ID.fullmatch(path.stem) or path.is_symlink() or path.stat().st_size > 40000:
            continue
        try:
            record = json.loads(path.read_text())
            if record.get('id') == path.stem and fingerprint(record['observation']) == path.stem:
                result.append(record)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return sorted(result, key=lambda r: (r['at'], r['id']), reverse=True)


@contextmanager
def locked(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Archivio esperienza non valido')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / 'library.lock'
    if path.is_symlink():
        raise ValueError('Archivio esperienza non valido')
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield root
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def disabled(root):
    path = Path(root) / 'excluded.json'
    if path.is_symlink():
        raise ValueError('Indice esperienza non valido')
    return set(json.loads(path.read_text())) if path.exists() else set()


def exclude(root, identifier, excluded=True):
    if not ID.fullmatch(identifier):
        raise ValueError('Esperienza non valida')
    with locked(root) as folder:
        from .lessons import entries as lessons
        if identifier not in {r['id'] for r in [*entries(folder), *lessons(folder)]}:
            raise ValueError('Esperienza non trovata')
        ids = disabled(folder)
        ids.add(identifier) if excluded else ids.discard(identifier)
        atomic_json(folder / 'excluded.json', sorted(ids))


def method_record(workspace, attempt):
    from .projects import artifact_path
    path = artifact_path(workspace, str(Path(attempt.get('output_dir', '')) / 'work/method.json'))
    trace = artifact_path(workspace, str(Path(attempt.get('output_dir', '')) / 'work/tool-events.json'))
    trace_ref = {'path': str(trace), 'sha256': digest(trace)} if trace else None
    generation = []
    work = Path(workspace) / Path(str(Path(attempt.get('output_dir', '')) / 'work')).relative_to('/mnt/user-data') if str(attempt.get('output_dir', '')).startswith('/mnt/user-data/') else None
    if work and work.resolve().is_relative_to(Path(workspace).resolve()) and not work.is_symlink():
        for candidate in sorted(work.glob('imagegen-*.json'))[:12]:
            report = artifact_path(workspace, '/mnt/user-data/' + candidate.relative_to(workspace).as_posix())
            if report and report.stat().st_size <= 16000:
                generation.append({'path': '/mnt/user-data/' + report.relative_to(workspace).as_posix(), 'sha256': digest(report)})
    if not path or path.stat().st_size > 16000:
        return {'status': 'not_recorded', 'tool_events': trace_ref, 'generation_records': generation, 'notice': 'Procedimento eseguito non registrato; non dedurlo dal risultato.'}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or not isinstance(value.get('approach'), str):
            raise ValueError()
        clean = {'approach': value['approach'][:1500]}
        for key in ('steps', 'limits'):
            items = value.get(key, [])
            if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                raise ValueError()
            clean[key] = [item[:1000] for item in items[:12]]
        scripts = []
        filenames = value.get('scripts', [])
        if not isinstance(filenames, list):
            raise ValueError()
        for filename in filenames[:12]:
            script = artifact_path(workspace, filename) if isinstance(filename, str) else None
            if script and script.stat().st_size <= 1048576 and script.suffix.lower() in ('.py', '.js', '.mjs', '.cjs', '.sh', '.json'):
                scripts.append({'path': filename, 'sha256': digest(script)})
        return redact_memory({'status': 'reported', 'path': str(path), 'sha256': digest(path),
                              'declared_method': clean, 'scripts': scripts, 'tool_events': trace_ref, 'generation_records': generation,
                              'notice': 'Procedimento dichiarato dal produttore, non rieseguito dal registro esperienza.'})
    except (OSError, ValueError, TypeError):
        return {'status': 'invalid', 'notice': 'Procedimento registrato in formato non utilizzabile.'}


def producer_role(workspace, attempt, roles):
    """Recover declared tool/procedure context from immutable legacy skill versions."""
    from .projects import artifact_path
    if attempt.get('role_scope'):
        return json.loads(read_document(workspace, attempt['role_scope']))
    identifier, version = attempt.get('role_id', ''), (attempt.get('context') or {}).get('role', '')
    current = roles.get(identifier, {})
    if current.get('version') == version:
        return current
    if not isinstance(identifier, str) or not ROLE_ID.fullmatch(identifier) or not isinstance(version, str) or not ID.fullmatch(version):
        return {}
    name = f'/mnt/user-data/.righaven-project/roles/{identifier}/{version}/SKILL.md'
    path = artifact_path(workspace, name)
    if not path or path.stat().st_size > 100000:
        return {}
    text = path.read_text()
    def section(title):
        marker = '## ' + title + '\n\n'
        return text.split(marker, 1)[1].split('\n\n## ', 1)[0] if text.count(marker) == 1 else ''
    try:
        tools, _ = json.JSONDecoder().raw_decode(section('Strumenti effettivi').lstrip())
        if not isinstance(tools, list) or any(not isinstance(t, dict) or not isinstance(t.get('id'), str) or not isinstance(t.get('version'), str) for t in tools):
            return {}
        return {'id': identifier, 'version': version,
                'procedure': [line[2:] for line in section('Metodo operativo').splitlines() if line.startswith('- ')][:12],
                'tools': [t['id'] for t in tools], 'tool_versions': {t['id']: t['version'] for t in tools},
                'skill': {'path': name, 'sha256': digest(path)}, 'scope_origin': 'saved_legacy_skill'}
    except (ValueError, TypeError):
        return {}


def collect(workspace, root, source_thread=None):
    """Capture evaluated criteria/corrections, not successful exits or model claims."""
    from .projects import locked as project_lock, load, artifact_path
    from .state import applications
    records = []
    captured = {r['observation'].get('capture_key') for r in entries(root)}
    with project_lock(workspace) as folder:
        project = load(folder, workspace)
        if not project:
            return 0
        roles = {r['id']: r for r in project.get('roles', [])}
        apps = {a['id']: a['version'] for a in applications()}
        for step in project['steps']:
            for attempt in step['attempts']:
                from .sandbox_lessons import observations as sandbox_observations
                try:
                    role = producer_role(workspace, attempt, roles)
                except (OSError, ValueError, KeyError):
                    role = {}
                records.extend(sandbox_observations(workspace, attempt, role, source_thread, captured))
                from .production_observations import observations as production_observations
                records.extend(production_observations(workspace, attempt, role, source_thread))
                review = attempt.get('quality_review') or {}
                target = artifact_path(workspace, review.get('product_path', ''))
                report = artifact_path(workspace, review.get('report_path', ''))
                if (not attempt.get('validated') or not target or not report
                        or digest(target) != review.get('sha256')
                        or review.get('report_sha256') and digest(report) != review['report_sha256']
                        or not ID.fullmatch(str(review.get('contract_hash', '')))):
                    continue
                # Scope reuse to the producer's tools, not the reviewer's toolset.
                producer = next((a for s in project['steps'] for a in reversed(s['attempts'])
                                 if review['product_path'] in a.get('output_files', [])), {})
                role = producer_role(workspace, producer, roles)
                if role.get('version') != (producer.get('context') or {}).get('role'):
                    role = {}
                tools = {t: role.get('tool_versions', {}).get(t, 'unknown') for t in role.get('tools', []) if t in apps}
                for criterion in review.get('criteria', []):
                    if criterion.get('status') not in ('passed', 'failed'):
                        continue
                    actions = [a for a in review.get('revision_actions', [])
                               if a.get('requirement_id') == criterion.get('requirement_id')]
                    observation = redact_memory({
                        'project_id': project['id'], 'source_thread': source_thread, 'product_sha256': review['sha256'],
                        'report_sha256': digest(report), 'contract_hash': review['contract_hash'],
                        'criterion': criterion.get('criterion', '')[:1000], 'method': criterion.get('method'),
                        'status': criterion['status'], 'evidence': criterion.get('evidence', '')[:1500],
                        'corrections': [a.get('action', '')[:1000] for a in actions[:3]],
                        'producer_method': method_record(workspace, producer),
                        'procedure': role.get('procedure', [])[:6], 'tools': tools, 'scope_known': bool(role),
                        'source_product': review['product_path'], 'source_report': review['report_path'],
                    })
                    observation['origin_id'] = fingerprint({k: observation[k] for k in ('project_id', 'product_sha256', 'report_sha256', 'contract_hash', 'criterion', 'method', 'status')})
                    records.append({'id': fingerprint(observation), 'at': attempt.get('finished_at') or utcnow(),
                                    'observation': observation})
    count = 0
    with locked(root) as folder:
        known = {r['observation'].get('origin_id') for r in entries(folder)}
        for record in records:
            if record['observation']['origin_id'] in known:
                continue
            path = folder / (record['id'] + '.json')
            if path.is_symlink():
                raise ValueError('Esperienza non valida')
            if not path.exists():
                atomic_json(path, record)
                known.add(record['observation']['origin_id'])
                count += 1
    return count


def select(root, specs, apps):
    """Select only generalized lessons; raw project facts never enter future skills."""
    from .lessons import entries as lessons, accepted, automatic, rank, category
    approved = accepted(root)
    auto = automatic(root)
    excluded = disabled(root)
    versions = {a['id']: a['version'] for a in apps}
    selected, covered = [], set()
    vocabulary = set(re.findall(r'\w{5,}', ' '.join(str(s) for s in specs).lower()))
    role_tools = {t for s in specs for t in s.get('tools', [])}
    candidates = []
    source_records = {r['id']:r['observation'] for r in entries(root)}
    for record in lessons(root):
        if record['id'] not in approved:
            continue
        basis = record['basis']
        # The newest generalization supersedes older text from the same source.
        sources = set(basis['source_ids'])
        if sources & covered:
            continue
        covered.update(sources)
        if record['id'] in excluded or sources & excluded:
            continue
        candidates.append(record)
    for record in sorted(candidates, key=rank):
        basis = record['basis']
        lesson = basis['lesson']
        tools = basis['tool_versions']
        if tools and (not set(tools).intersection(role_tools) or not set(tools).issubset(versions)):
            continue
        changed = {t:{'observed':v,'current':versions[t]} for t,v in tools.items() if versions[t] != v}
        if changed and category(record, source_records) == 'tool_operation':
            continue
        words = set(re.findall(r'\w{5,}', json.dumps(lesson, ensure_ascii=False).lower()))
        if not tools and len(words & vocabulary) < 2:
            continue
        portable = {'id': record['id'], 'lesson': lesson, 'tool_versions': tools,
                    'current_tool_versions':{t:versions[t] for t in tools}, 'version_changes':changed,
                    'source_ids': basis['source_ids'], 'source_statuses': basis.get('source_statuses', []),
                    'notice': ('Conoscenza tecnica attivata dopo test automatico; non prova la qualità del prodotto.' if record['id'] in auto else 'Metodo accettato dall’utente.') + ' Verifica condizioni, limiti e pertinenza; le misure del vecchio caso non sono una promessa per questo progetto.'}
        if changed:
            portable['notice'] += ' Gli strumenti sono stati aggiornati: conserva il principio del metodo accettato, verifica comandi e API nella versione corrente; la prova storica non certifica la nuova CLI.'
        if sum(len(json.dumps(r)) for r in selected) + len(json.dumps(portable)) > 14000:
            continue
        selected.append(portable)
        if len(selected) == 6:
            break
    return selected


def snapshot(workspace, root, specs, apps):
    selected = select(root, specs, apps)
    text = json.dumps({'notice': 'Solo metodi accettati dall’utente e conoscenze tecniche con test automatico superato, non fatti dei vecchi progetti. Verifica pertinenza, condizioni, strumenti e richiesta attuale. '
                       'Le evidenze specifiche restano nell’archivio di origine; non trasferire personaggi, eventi, scelte o file del vecchio progetto.',
                       'lessons': selected}, ensure_ascii=False, sort_keys=True)
    document = scoped_file(workspace, 'experience/' + fingerprint(text) + '.json', text)
    return {**document, 'count': len(selected), 'ids': [r['id'] for r in selected]}


def summary(root, export=False, *, source_thread=None):
    from .lessons import entries as lessons, pending, accepted, automatic, category, rank
    excluded = disabled(root)
    records, generalized = entries(root), lessons(root)
    approved = accepted(root)
    auto = automatic(root)
    sources = {r['id']: r['observation'] for r in records}
    thread_sources = {r['id'] for r in records if r['observation'].get('source_thread') == source_thread}
    current = [r for r in records if r['id'] in thread_sources]
    all_pending = pending(root, limit=1000000)
    visible = records if export else (current + [r for r in records if r['id'] not in thread_sources])[:200]
    return {'total': len(records), 'excluded': len(excluded), 'pending': len(all_pending),
            'current_project': {'thread_id':source_thread, 'observations':len(current),
                'pending':sum(s.get('source_thread') == source_thread for s in all_pending),
                'meaningful':len(pending(root,limit=1000000,source_thread=source_thread,meaningful_only=True)) if source_thread else 0,
                'lessons':sum(bool(set(r['basis']['source_ids']) & thread_sources) for r in generalized),
                'lesson_ids':[r['id'] for r in generalized if set(r['basis']['source_ids']) & thread_sources]},
            'lessons': [{**r, 'accepted': r['id'] in approved, 'category': category(r, sources),
                         'approval': 'automatic' if r['id'] in auto else 'manual' if r['id'] in approved else 'pending',
                         'excluded': r['id'] in excluded or bool(set(r['basis']['source_ids']) & excluded)} for r in sorted(generalized, key=rank)],
            'observations': [{**r, 'excluded': r['id'] in excluded} for r in visible]}


def prefer(workspace, root, delivery_id, note, source_thread=None):
    """Explicit user preference for a method; never marks a project ready or a test passed."""
    from .projects import locked as project_lock, load, artifact_path
    if not isinstance(note, str) or not 5 <= len(note.strip()) <= 2000:
        raise ValueError('Descrivi cosa vuoi riutilizzare (5–2000 caratteri)')
    with project_lock(workspace) as folder:
        project = load(folder, workspace)
        attempt = next((a for s in (project or {}).get('steps', []) for a in s['attempts']
                        if Path(a.get('output_dir', '')).name == delivery_id and a.get('validated')), None)
        if not attempt:
            raise ValueError('Scegli una lavorazione conclusa con file verificati')
        files = []
        for name in attempt.get('output_files', []):
            path = artifact_path(workspace, name)
            if path:
                files.append({'path': name, 'sha256': digest(path)})
        if not files:
            raise ValueError('I file del metodo non sono più disponibili')
        role = producer_role(workspace, attempt, {r['id']: r for r in project.get('roles', [])})
        role_skill = role.get('skill') or next((r.get('skill') for r in project.get('roles', []) if r.get('version') == role.get('version')), None)
        observation = redact_memory({
            'kind': 'user_preference', 'project_id': project['id'], 'source_thread': source_thread,
            'criterion': note.strip(), 'method': 'user_feedback', 'status': 'preferred_by_user',
            'evidence': 'Preferenza espressa dall’utente per questa lavorazione; non è un collaudo tecnico o un risultato riproducibile garantito.',
            'corrections': [], 'producer_method': method_record(workspace, attempt), 'procedure': role.get('procedure', []),
            'tools': {t: role.get('tool_versions', {}).get(t, 'unknown') for t in role.get('tools', [])},
            'scope_known': bool(role), 'models': (attempt.get('context') or {}).get('provider', {}),
            'role_skill': role_skill, 'files': files,
            'product_sha256': fingerprint(files), 'report_sha256': '',
            'contract_hash': (project.get('acceptance') or {}).get('hash'),
            'limitations': (attempt.get('delivery_record') or {}).get('issues', []),
            'instruction': 'Considera questo metodo come candidato preferito; riscopri le capacità disponibili, '
                           'confronta il brief attuale e verifica un campione. Le versioni sconosciute non sono compatibilità accertata.',
        })
        observation['origin_id'] = fingerprint(observation)
        record = {'id': fingerprint(observation), 'at': utcnow(), 'observation': observation}
    with locked(root) as folder:
        path = folder / (record['id'] + '.json')
        if not path.exists():
            atomic_json(path, record)
    return record['id']
