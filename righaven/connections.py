"""User database and Microsoft cloud connections, assigned to projects and delivered per assignment.

Access is the user's choice: the connections the user assigns to a task are
delivered to every assignment of that task, and to no other. Secrets are
encrypted at rest with the installation credentials key and decrypted only into
a private folder mounted read-only into each worker, deleted when it ends. Coordinators, project context, receipts and logs see public
metadata only: name, kind, host, database and the read-only declaration.
"""
import ipaddress
import json
import re
import shutil
import socket
import time
from pathlib import Path
from urllib.parse import quote

from . import state

KINDS = ('postgres', 'sqlserver', 'mysql', 'oracle', 'entra')
CONNECTION_ID = re.compile(r'[a-z][a-z0-9-]{1,39}\Z')
HOST = re.compile(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z')
NAME = re.compile(r'[A-Za-z0-9_.@$#-]{1,128}\Z')
GUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z')
TENANT = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})+)\Z')
DEFAULT_PORTS = {'postgres': 5432, 'sqlserver': 1433, 'mysql': 3306, 'oracle': 1521}
AUTHORITIES = {'public': 'login.microsoftonline.com', 'usgov': 'login.microsoftonline.us', 'china': 'login.chinacloudapi.cn'}
SECRETS = ('password', 'client_secret')
MAX_CONNECTIONS = 50
MOUNT = '/run/righaven/connections'
# Domains an assignment needs to obtain Entra tokens and call Fabric / Power BI (allowlist egress mode).
ENTRA_DOMAINS = {'public': ['login.microsoftonline.com', 'api.fabric.microsoft.com', '.fabric.microsoft.com', 'api.powerbi.com', '.analysis.windows.net'],
                 'usgov': ['login.microsoftonline.us', '.fabric.microsoft.us', 'api.powerbigov.us'],
                 'china': ['login.chinacloudapi.cn', 'app.powerbi.cn']}


def folder(user_id):
    from righaven_core.config.paths import get_paths
    path = get_paths().user_dir(str(user_id)) / 'righaven-connections'
    if path.is_symlink():
        raise ValueError('Archivio connessioni non valido')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _cipher():
    from .tenant_profiles import cipher
    return cipher()


def _path(user_id, identifier):
    if not CONNECTION_ID.fullmatch(str(identifier or '')):
        raise ValueError('ID connessione: lettere minuscole, cifre e trattini')
    return folder(user_id) / (identifier + '.json')


def _read(user_id, identifier):
    path = _path(user_id, identifier)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Connessione non trovata: ' + identifier)
    stored = json.loads(path.read_text())
    secret = json.loads(_cipher().decrypt(stored['encrypted'].encode()).decode()) if stored.get('encrypted') else {}
    return {**stored['public'], **secret}


def _write(user_id, record):
    public = {k: v for k, v in record.items() if k not in SECRETS}
    secret = {k: record[k] for k in SECRETS if record.get(k)}
    encrypted = _cipher().encrypt(json.dumps(secret).encode()).decode() if secret else ''
    state.atomic_json(_path(user_id, record['id']), {'format': 'fernet:v2', 'public': public, 'encrypted': encrypted})
    _path(user_id, record['id']).chmod(0o600)


def public_view(record):
    value = {k: v for k, v in record.items() if k not in SECRETS}
    value['has_secret'] = bool(record.get('password') or record.get('client_secret'))
    value['tools'] = usable_tools(record)
    return value


def usable_tools(record):
    if record['kind'] == 'entra':
        return []
    if record['kind'] == 'sqlserver' and record.get('authentication') == 'entra':
        return ['usql']
    return ['usql', 'dlt', 'schemacrawler']


def _text(value, label, pattern=None, limit=200, required=True):
    if value in (None, '') and not required:
        return ''
    if not isinstance(value, str) or not value.strip() or len(value) > limit or (pattern and not pattern.fullmatch(value.strip())):
        raise ValueError('Campo non valido: ' + label)
    return value.strip()


def validate(body, previous=None):
    """Normalized record; secrets left empty on update keep their stored value."""
    if not isinstance(body, dict):
        raise ValueError('Connessione non valida')
    kind = body.get('kind') or (previous or {}).get('kind')
    if kind not in KINDS:
        raise ValueError('Tipo di connessione tra ' + ', '.join(KINDS))
    if previous and previous['kind'] != kind:
        raise ValueError('Il tipo di una connessione non si cambia: creane una nuova')
    record = {'id': _text(body.get('id') or (previous or {}).get('id'), 'id', CONNECTION_ID, 40), 'kind': kind,
              'name': _text(body.get('name'), 'nome', None, 80), 'description': _text(body.get('description'), 'descrizione', None, 400, False)}
    if kind == 'entra':
        record.update(tenant_id=_text(body.get('tenant_id'), 'tenant (ID o dominio)', TENANT, 120),
                      client_id=_text(body.get('client_id'), 'ID applicazione (client)', GUID, 36),
                      cloud=body.get('cloud', 'public'))
        if record['cloud'] not in AUTHORITIES:
            raise ValueError('Cloud Microsoft tra ' + ', '.join(AUTHORITIES))
        record['client_secret'] = body.get('client_secret') or (previous or {}).get('client_secret') or ''
        if not record['client_secret'] or len(record['client_secret']) > 512:
            raise ValueError('Segreto client dell’applicazione Entra obbligatorio')
        return record
    port = body.get('port') or DEFAULT_PORTS[kind]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Porta tra 1 e 65535')
    record.update(host=_text(body.get('host'), 'host', HOST, 253), port=port,
                  database=_text(body.get('database'), 'database', NAME, 128),
                  read_only=body.get('read_only') is True, tls=body.get('tls', True) is not False)
    authentication = body.get('authentication', 'password') if kind == 'sqlserver' else 'password'
    if authentication not in ('password', 'entra'):
        raise ValueError('Autenticazione SQL Server: password o entra')
    record['authentication'] = authentication
    if authentication == 'entra':
        record['entra_connection'] = _text(body.get('entra_connection'), 'connessione Entra', CONNECTION_ID, 40)
        return record
    record['username'] = _text(body.get('username'), 'utente', NAME, 128)
    record['password'] = body.get('password') or (previous or {}).get('password') or ''
    if not record['password'] or len(record['password']) > 512:
        raise ValueError('Password obbligatoria')
    return record


def listing(user_id):
    rows = []
    for path in sorted(folder(user_id).glob('*.json')):
        try:
            rows.append(public_view(_read(user_id, path.stem)))
        except (ValueError, OSError, KeyError):
            continue
    return rows


def save(user_id, body, identifier=None):
    previous = _read(user_id, identifier) if identifier else None
    if identifier and body.get('id') not in (None, identifier):
        raise ValueError('L’ID di una connessione non si cambia')
    record = validate({**body, 'id': identifier or body.get('id')}, previous)
    if not identifier and _path(user_id, record['id']).exists():
        raise ValueError('Esiste già una connessione con questo ID')
    if not identifier and len(list(folder(user_id).glob('*.json'))) >= MAX_CONNECTIONS:
        raise ValueError('Al massimo ' + str(MAX_CONNECTIONS) + ' connessioni per utente')
    if record.get('authentication') == 'entra':
        entra = _read(user_id, record['entra_connection'])
        if entra['kind'] != 'entra':
            raise ValueError('La connessione indicata non è un’applicazione Microsoft Entra ID')
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    record.update(created_at=(previous or {}).get('created_at', now), updated_at=now)
    if previous and previous.get('last_test') and all(previous.get(k) == record.get(k) for k in ('host', 'port', 'tenant_id', 'client_id')):
        record['last_test'] = previous['last_test']
    _write(user_id, record)
    return public_view(record)


def delete(user_id, identifier):
    path = _path(user_id, identifier)
    if not path.is_file():
        raise ValueError('Connessione non trovata: ' + identifier)
    dependants = [r['id'] for r in listing(user_id) if r.get('entra_connection') == identifier]
    if dependants:
        raise ValueError('Usata dalle connessioni ' + ', '.join(dependants) + ': eliminale o cambiane l’autenticazione prima')
    path.unlink()


def _private_allowed():
    import os
    return os.getenv('RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS', '').lower() in ('1', 'allow', 'true')


def _addresses(host, port):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError('Nome host non risolto: ' + host) from error
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    private = [a for a in addresses if not ipaddress.ip_address(a).is_global]
    if private and not _private_allowed():
        raise ValueError('L’host risolve in un indirizzo privato o interno (' + private[0] + '): l’amministratore può consentirlo con '
                         'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS=allow')
    return addresses


def test(user_id, identifier):
    """Reachability for databases, a real token request for Entra; authentication of databases is proven at first use."""
    record = _read(user_id, identifier)
    started = time.time()
    try:
        if record['kind'] == 'entra':
            import httpx
            authority = AUTHORITIES[record['cloud']]
            response = httpx.post(f'https://{authority}/{quote(record["tenant_id"])}/oauth2/v2.0/token', timeout=15,
                                  data={'grant_type': 'client_credentials', 'client_id': record['client_id'],
                                        'client_secret': record['client_secret'], 'scope': 'https://database.windows.net/.default'})
            if response.status_code == 200 and response.json().get('access_token'):
                result = {'ok': True, 'detail': 'Token Microsoft Entra ID ottenuto per l’applicazione ' + record['client_id']}
            else:
                payload = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                codes = payload.get('error_codes') or []
                result = {'ok': False, 'detail': 'Entra ID ha rifiutato le credenziali: ' + str(payload.get('error') or response.status_code)
                          + (' (AADSTS' + str(codes[0]) + ')' if codes else '')}
        else:
            addresses = _addresses(record['host'], record['port'])
            with socket.create_connection((addresses[0], record['port']), timeout=6):
                pass
            result = {'ok': True, 'detail': record['host'] + ':' + str(record['port']) + ' raggiungibile; utente e password si verificano al primo utilizzo in un incarico'}
    except (OSError, ValueError) as error:
        result = {'ok': False, 'detail': str(error)[:300]}
    except Exception as error:  # httpx and DNS errors must not expose secrets either
        result = {'ok': False, 'detail': type(error).__name__}
    result.update(at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seconds=round(time.time() - started, 2))
    _write(user_id, {**record, 'last_test': result})
    return result


# --- Projects -------------------------------------------------------------------------

def assign(user_id, workspace, identifiers):
    if not isinstance(identifiers, list) or len(identifiers) > 10 or len(set(identifiers)) != len(identifiers):
        raise ValueError('Assegna al massimo 10 connessioni diverse')
    for identifier in identifiers:
        _read(user_id, identifier)
    from .project_store import locked, load
    with locked(workspace) as directory:
        value = load(directory, workspace)
        if not value:
            raise ValueError('Avvia prima il lavoro: le connessioni si assegnano a un lavoro esistente')
        value['connections'] = {'owner': str(user_id), 'ids': list(identifiers), 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        state.atomic_json(directory / 'project.json', value)
    return assigned(workspace)


def assigned(workspace, value=None):
    """Public metadata of the project's connections, for the coordinator and the project panel."""
    if value is None:
        from .project_store import locked, load
        with locked(workspace) as directory:
            value = load(directory, workspace) or {}
    binding = value.get('connections') or {}
    rows = []
    for identifier in binding.get('ids', []):
        try:
            record = _read(binding['owner'], identifier)
        except (ValueError, OSError, KeyError):
            rows.append({'id': identifier, 'missing': True})
            continue
        view = public_view(record)
        rows.append({k: view.get(k) for k in ('id', 'name', 'kind', 'host', 'port', 'database', 'read_only', 'authentication', 'cloud', 'tools', 'description')
                     if view.get(k) not in (None, '')})
    return rows


# --- Assignment delivery -------------------------------------------------------------------

def _file(record, user_id):
    """The private connection file the data adapters read; never logged or retained."""
    kind = record['kind']
    if kind == 'entra':
        return {'kind': 'entra', 'tenant_id': record['tenant_id'], 'client_id': record['client_id'], 'client_secret': record['client_secret'],
                'authority_host': AUTHORITIES[record['cloud']], 'cloud': record['cloud']}
    host, port, database = record['host'], record['port'], record['database']
    base = {'kind': kind, 'host': host, 'port': port, 'database': database, 'read_only': record['read_only']}
    if record.get('authentication') == 'entra':
        entra = _read(user_id, record['entra_connection'])
        user = quote(entra['client_id'] + '@' + entra['tenant_id'], safe='')
        return {**base, 'authentication': 'entra',
                'usql_url': f'azuresql://{user}:{quote(entra["client_secret"], safe="")}@{host}:{port}?database={quote(database)}'
                            f'&fedauth=ActiveDirectoryServicePrincipal&encrypt=true'}
    user, password = quote(record['username'], safe=''), quote(record['password'], safe='')
    if kind == 'postgres':
        ssl = 'require' if record['tls'] else 'disable'
        return {**base, 'url': f'postgresql+psycopg://{user}:{password}@{host}:{port}/{quote(database)}?sslmode={ssl}',
                'jdbc_url': f'jdbc:postgresql://{host}:{port}/{database}?sslmode={ssl}', 'username': record['username'], 'password': record['password']}
    if kind == 'oracle':
        service = quote(database, safe='')
        return {**base, 'url': f'oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service}',
                'usql_url': f'oracle://{user}:{password}@{host}:{port}/{service}',
                'jdbc_url': f'jdbc:oracle:thin:@//{host}:{port}/{database}', 'username': record['username'], 'password': record['password']}
    if kind == 'mysql':
        return {**base, 'url': f'mysql+pymysql://{user}:{password}@{host}:{port}/{quote(database)}',
                'jdbc_url': f'jdbc:mysql://{host}:{port}/{database}' + ('?sslMode=REQUIRED' if record['tls'] else ''),
                'username': record['username'], 'password': record['password']}
    encrypt = 'true' if record['tls'] else 'false'
    return {**base, 'url': f'mssql+pymssql://{user}:{password}@{host}:{port}/{quote(database)}',
            'usql_url': f'sqlserver://{user}:{password}@{host}:{port}?database={quote(database)}&encrypt={encrypt}',
            'jdbc_url': f'jdbc:sqlserver://{host}:{port};databaseName={database};encrypt={encrypt};trustServerCertificate=false',
            'username': record['username'], 'password': record['password']}


class Delivery:
    """Decrypt the task's connections, chosen by the user, into a private folder for one worker; removed on close."""
    def __init__(self, workspace, destination):
        self.directory = None
        self.public = []
        self.domains = []
        from .project_store import locked, load
        with locked(workspace) as directory:
            value = load(directory, workspace) or {}
        binding = value.get('connections') or {}
        wanted = list(binding.get('ids') or [])
        if not wanted:
            return
        owner = binding['owner']
        self.directory = Path(destination)
        self.directory.mkdir(parents=True, mode=0o700)
        for identifier in wanted:
            try:
                record = _read(owner, identifier)
            except (ValueError, OSError, KeyError):
                continue  # deleted after assignment: nothing to deliver
            path = self.directory / (identifier + '.json')
            path.write_text(json.dumps(_file(record, owner)))
            path.chmod(0o600)
            self.public.append({k: v for k, v in public_view(record).items() if k in ('id', 'name', 'kind', 'host', 'port', 'database', 'read_only', 'authentication', 'tools')})
            entra_cloud = record.get('cloud') if record['kind'] == 'entra' else (_read(owner, record['entra_connection']).get('cloud') if record.get('authentication') == 'entra' else None)
            if entra_cloud:
                self.domains += ENTRA_DOMAINS[entra_cloud]

    def mount_arguments(self, mount):
        return ['--mount', mount(self.directory, MOUNT, True)] if self.directory else []

    def close(self):
        if self.directory:
            shutil.rmtree(self.directory, ignore_errors=True)
