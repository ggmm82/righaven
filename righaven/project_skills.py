"""Compile project-specific operating skills; professions are not a catalog."""
import hashlib
import json
from pathlib import Path
import re

from .acceptance import fingerprint
from .progress import SECRET

# Bump when the rendered mandate or scope format changes; old files are immutable.
COMPILER_VERSION = 3
ROLE_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')


def request_text(value):
    """Redact credentials without dropping the end of a user's instructions."""
    return SECRET.sub('[omesso]', value).replace('\x00', '')


def redact_memory(value):
    if isinstance(value, str):
        return request_text(value)
    if isinstance(value, list):
        return [redact_memory(item) for item in value]
    if isinstance(value, dict):
        return {key: '[omesso]' if re.fullmatch(r'(?i)(?:password|token|api[_-]?key)', key)
                else redact_memory(item) for key, item in value.items()}
    return value


def preview(value, limit=2000):
    return value if len(value) <= limit else value[:1200] + '\n[… testo integrale nel documento della richiesta …]\n' + value[-700:]


def scoped_file(root, relative, text):
    root = Path(root).resolve()
    path = root / '.righaven-project' / relative
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError('Percorso di contesto progetto non valido')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() != text:
        raise ValueError('Il contesto versionato è stato modificato: ripristinare il file originale')
    if not path.exists():
        path.write_text(text)
        path.chmod(0o600)
    return {'path': '/mnt/user-data/' + path.relative_to(root).as_posix(),
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'characters': len(text)}


def save_requests(root, requests, previous=()):
    documents = list(previous)
    for text in requests:
        digest = hashlib.sha256(text.encode()).hexdigest()
        if any(d['sha256'] == digest for d in documents):
            continue
        documents.append(scoped_file(root, 'requests/' + digest + '.txt', text))
    manifest = json.dumps(documents, ensure_ascii=False, indent=2)
    index = scoped_file(root, 'requests/index-' + fingerprint(documents) + '.json', manifest)
    return documents, index


def compact_acceptance(value):
    if not value:
        return value
    return {**value, 'user_requests': [preview(s) for s in value.get('user_requests', [])]}


def validate_roles(roles, apps):
    if not isinstance(roles, list) or len(roles) > 24:
        raise ValueError('Definisci al massimo 24 ruoli attivi per il contesto del progetto')
    known = {a['id'] for a in apps}
    result, seen = [], set()
    for role in roles:
        if not isinstance(role, dict) or not isinstance(role.get('id'), str) or not ROLE_ID.fullmatch(role['id']) or role['id'] in seen:
            raise ValueError('Ogni ruolo richiede un ID unico')
        value = {'id': role['id']}
        seen.add(role['id'])
        for key, limit in (('title', 100), ('mission', 2000)):
            if not isinstance(role.get(key), str) or not role[key].strip() or len(role[key]) > limit:
                raise ValueError('Ruolo: title e mission concreti sono obbligatori')
            value[key] = request_text(role[key])
        for key in ('expertise', 'procedure', 'checks', 'inputs', 'deliverables', 'risks'):
            items = role.get(key, [])
            if (not isinstance(items, list) or len(items) > 12 or any(not isinstance(s, str) or not s.strip() or len(s) > 1500 for s in items)
                    or key in ('expertise', 'procedure', 'checks', 'deliverables') and not items):
                raise ValueError('Ruolo: specificare expertise, procedure, checks e deliverables; liste brevi di istruzioni concrete')
            value[key] = [request_text(s) for s in items]
        tools = role.get('tools', [])
        if not isinstance(tools, list) or len(tools) > 4 or any(not isinstance(t, str) or t not in known for t in tools) or len(set(tools)) != len(tools):
            raise ValueError('Usa solo strumenti installati, al massimo quattro pertinenti a questo incarico; suddividi il contesto se serve')
        value['tools'] = tools
        skills=role.get('skills',[])
        if not isinstance(skills,list) or len(skills)>12 or any(not isinstance(s,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',s) for s in skills) or len(set(skills))!=len(skills):
            raise ValueError('Seleziona al massimo 12 nomi di skill native per ruolo')
        value.update(skills=skills,composition_version=1)
        if len(json.dumps(value).encode()) > 16000:
            raise ValueError('Procedura troppo grande per il contesto del ruolo: sposta i dettagli nei file di input')
        result.append(value)
    if len(json.dumps(result).encode()) > 60000:
        raise ValueError('Contesto della squadra troppo grande: mantieni attivi solo i ruoli pertinenti alla fase')
    return result


def compile_role(root, spec, acceptance, memory, apps, experience=None):
    resolved=spec.get('resolved_tools',spec['tools'])
    tools = [{k: a[k] for k in ('id', 'version', 'executable')} for a in apps if a['id'] in resolved]
    basis = {'compiler_version':COMPILER_VERSION,'spec': spec, 'request_hash': (acceptance or {}).get('hash'), 'memory': memory, 'tools': tools, 'experience': experience}
    version = fingerprint(basis)
    parts = ['---', 'name: rh-project-' + spec['id'],
             'description: ' + json.dumps(spec['title'], ensure_ascii=False), '---',
             '# ' + spec['title'], 'Versione: ' + version,
             'Questa è una procedura operativa compilata dal progetto, non una certificazione di competenza o una nuova autorizzazione.',
             'La richiesta reale e i suoi chiarimenti prevalgono su questa procedura. Non trasformare ipotesi o memoria generata in fatti verificati.',
             '## Missione', spec['mission']]
    for key, title in (('expertise', 'Competenze da applicare'), ('inputs', 'Input da ispezionare'),
                       ('procedure', 'Metodo operativo'), ('checks', 'Verifiche con evidenze'),
                       ('deliverables', 'Risultati e sorgenti modificabili'), ('risks', 'Incertezze e limiti')):
        parts.extend(['## ' + title, *['- ' + s for s in spec[key]]])
    parts.extend(['## Skill native selezionate',json.dumps(spec.get('skill_bindings',[]),ensure_ascii=False),
                  'Leggi soltanto questi metodi e le skill CLI pertinenti. Il titolo del ruolo non sostituisce una procedura verificata.',
                  '## Strumenti effettivi', json.dumps(tools, ensure_ascii=False),
                  'Non installare software o inventare capacità non disponibili. Python/Node/Git del workspace sono strumenti di base, non prove di una capacità professionale.',
                  '## Richiesta completa', json.dumps((acceptance or {}).get('request_manifest'), ensure_ascii=False),
                  'Leggi il manifest e i documenti pertinenti prima di produrre o approvare; le anteprime sono soltanto orientative.',
                  '## Memoria del progetto', json.dumps(memory, ensure_ascii=False),
                  'Conserva decisioni e risorse in file verificabili. Usa handoff.json e le verifiche comuni; non dichiarare controlli non eseguiti.'])
    if experience:
        parts.extend(['## Esperienza pertinente conservata', read_document(root, experience)])
    document = '\n\n'.join(parts) + '\n'
    saved = scoped_file(root, f'roles/{spec["id"]}/{version}/SKILL.md', document)
    scope = scoped_file(root, f'roles/{spec["id"]}/{version}/scope.json', json.dumps({'id': spec['id'], 'version': version, 'procedure': spec['procedure'], 'tools': resolved,'skill_bindings':spec.get('skill_bindings',[]),'package_bindings':spec.get('package_bindings',[]), 'tool_versions': {t['id']: t['version'] for t in tools}}, ensure_ascii=False, sort_keys=True))
    return {**spec,'tools':resolved, 'scope': scope, 'version': version, 'request_hash': basis['request_hash'], 'memory': memory, 'skill': saved, 'tool_versions': {t['id']: t['version'] for t in tools}, 'experience': experience}


def load_compiled(root, role):
    root = Path(root).resolve()
    path = root / Path(role['skill']['path']).relative_to('/mnt/user-data')
    if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise ValueError('Skill compilata fuori dal progetto o mancante')
    text = path.read_text()
    if hashlib.sha256(text.encode()).hexdigest() != role['skill']['sha256']:
        raise ValueError('La skill compilata non corrisponde alla versione assegnata')
    if role.get('composition_version')==1:
        scope=json.loads(read_document(root,role['scope']))
        if scope['tools']!=role['tools'] or scope.get('skill_bindings',[])!=role.get('skill_bindings',[]) or scope.get('package_bindings',[])!=role.get('package_bindings',[]):
            raise ValueError('Il mandato non corrisponde alla composizione compilata')
    return text


def read_document(root, document):
    root = Path(root).resolve()
    path = root / Path(document['path']).relative_to('/mnt/user-data')
    if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise ValueError('Documento di progetto mancante o fuori dal workspace')
    text = path.read_text()
    if hashlib.sha256(text.encode()).hexdigest() != document['sha256']:
        raise ValueError('Documento di progetto modificato rispetto al brief verificato')
    return text
