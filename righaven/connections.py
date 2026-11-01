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
TENANT = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})+|organizations|common)\Z')
DEFAULT_PORTS = {'postgres': 5432, 'sqlserver': 1433, 'mysql': 3306, 'oracle': 1521}
AUTHORITIES = {'public': 'login.microsoftonline.com', 'usgov': 'login.microsoftonline.us', 'china': 'login.chinacloudapi.cn'}
SECRETS = ('password', 'client_secret', 'refresh_token', 'device_code')
# Personal Microsoft accounts sign in with the device code flow, so multi-factor authentication and
# Conditional Access happen on Microsoft's page; RigHaven never sees the password. The default public
# client is the Microsoft Azure CLI application, pre-authorized for Azure SQL in most tenants; an
# organization may register its own public client and set its ID instead.
PUBLIC_CLIENT = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
SQL_SCOPES = {'public': 'https://database.windows.net/.default', 'usgov': 'https://database.usgovcloudapi.net/.default',
              'china': 'https://database.chinacloudapi.cn/.default'}
FABRIC_SCOPE = 'https://api.fabric.microsoft.com/.default'
ENTRA_MODES = ('user', 'application')
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
    value['has_secret'] = bool(record.get('password') or record.get('client_secret') or record.get('refresh_token'))
    if record['kind'] == 'entra':
        value['mode'] = entra_mode(record)
        value['signed_in'] = bool(record.get('refresh_token'))
    value['tools'] = usable_tools(record)
    return value


def entra_mode(record):
    return record.get('mode') or 'application'  # connections saved before personal sign-in were applications


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
        mode = body.get('mode') or (entra_mode(previous) if previous else 'user')
        if mode not in ENTRA_MODES:
            raise ValueError('Microsoft Entra ID: personal account (user) or application')
        record.update(mode=mode, tenant_id=_text(body.get('tenant_id') or ('organizations' if mode == 'user' else ''), 'tenant (ID o dominio)', TENANT, 120),
                      client_id=_text(body.get('client_id') or (PUBLIC_CLIENT if mode == 'user' else ''), 'ID applicazione (client)', GUID, 36),
                      cloud=body.get('cloud', 'public'))
        if record['cloud'] not in AUTHORITIES:
            raise ValueError('Cloud Microsoft tra ' + ', '.join(AUTHORITIES))
        if mode == 'user':
            # A sign-in belongs to the tenant, client and cloud it was made for.
            same = previous and all(previous.get(k) == record[k] for k in ('tenant_id', 'client_id', 'cloud')) and entra_mode(previous) == 'user'
            if same:
                record.update({k: previous[k] for k in ('refresh_token', 'account', 'account_name', 'signed_in_at') if previous.get(k)})
            return record
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
            raise ValueError('La connessione indicata non è un account o un’applicazione Microsoft Entra ID')
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
        if record['kind'] == 'entra' and entra_mode(record) == 'user':
            if not record.get('refresh_token'):
                result = {'ok': False, 'detail': 'Sign in with Microsoft first'}
            else:
                _access_token(user_id, record, SQL_SCOPES[record['cloud']])
                result = {'ok': True, 'detail': 'Token Microsoft Entra ID ottenuto per l’account ' + str(record.get('account') or '')}
                record = _read(user_id, identifier)  # keep the rotated refresh token
        elif record['kind'] == 'entra':
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


# --- Personal Microsoft sign-in (OAuth2 device code, MFA on Microsoft's page) ---------------

def _endpoint(record, name):
    return f'https://{AUTHORITIES[record["cloud"]]}/{quote(record["tenant_id"])}/oauth2/v2.0/{name}'


def _post(url, data):
    import httpx
    try:
        response = httpx.post(url, data=data, timeout=15)
    except httpx.HTTPError as error:
        raise ValueError('Microsoft sign-in service unreachable: ' + type(error).__name__) from None
    payload = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
    return response.status_code, payload


def _personal(user_id, identifier):
    record = _read(user_id, identifier)
    if record['kind'] != 'entra' or entra_mode(record) != 'user':
        raise ValueError('Microsoft sign-in is available for personal Microsoft Entra ID connections')
    return record


def _error(payload, status):
    codes = payload.get('error_codes') or []
    return str(payload.get('error') or status) + (' (AADSTS' + str(codes[0]) + ')' if codes else '')


def _claims(id_token):
    import base64
    try:
        part = id_token.split('.')[1]
        return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
    except (IndexError, ValueError):
        return {}


def sign_in(user_id, identifier):
    """Start the device code flow: the user opens Microsoft's page, enters the code and completes MFA there."""
    record = _personal(user_id, identifier)
    status, payload = _post(_endpoint(record, 'devicecode'), {'client_id': record['client_id'], 'scope': SQL_SCOPES[record['cloud']] + ' offline_access openid profile'})
    if status != 200 or not payload.get('device_code'):
        raise ValueError('Microsoft refused the sign-in request: ' + _error(payload, status))
    expires = int(time.time()) + int(payload.get('expires_in', 900))
    _write(user_id, {**record, 'device_code': payload['device_code'], 'sign_in_expires': expires})
    return {'user_code': payload['user_code'], 'verification_uri': payload['verification_uri'], 'expires_in': int(payload.get('expires_in', 900)),
            'interval': int(payload.get('interval', 5)), 'message': payload.get('message', '')}


def complete_sign_in(user_id, identifier):
    """Poll once; the browser repeats at the interval Microsoft asked for."""
    record = _personal(user_id, identifier)
    if not record.get('device_code') or record.get('sign_in_expires', 0) < time.time():
        _write(user_id, {k: v for k, v in record.items() if k not in ('device_code', 'sign_in_expires')})
        return {'status': 'expired'}
    status, payload = _post(_endpoint(record, 'token'), {
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'client_id': record['client_id'], 'device_code': record['device_code']})
    if status == 200 and payload.get('refresh_token'):
        claims = _claims(payload.get('id_token', ''))
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        account = str(claims.get('preferred_username') or claims.get('upn') or claims.get('email') or '')[:200]
        signed = {k: v for k, v in record.items() if k not in ('device_code', 'sign_in_expires')}
        signed.update(refresh_token=payload['refresh_token'], account=account, account_name=str(claims.get('name') or '')[:200], signed_in_at=now,
                      last_test={'ok': True, 'detail': 'Accesso Microsoft completato per ' + account, 'at': now, 'seconds': 0})
        _write(user_id, signed)
        return {'status': 'signed_in', 'account': account}
    error = payload.get('error')
    if error in ('authorization_pending', 'slow_down'):
        return {'status': 'pending', 'interval': 10 if error == 'slow_down' else 5}
    _write(user_id, {k: v for k, v in record.items() if k not in ('device_code', 'sign_in_expires')})
    if error in ('expired_token', 'code_expired'):
        return {'status': 'expired'}
    if error in ('authorization_declined', 'access_denied'):
        return {'status': 'declined'}
    # For example AADSTS53003: Conditional Access blocks the device code flow for this tenant.
    return {'status': 'failed', 'detail': _error(payload, status)}


def sign_out(user_id, identifier):
    record = _personal(user_id, identifier)
    _write(user_id, {k: v for k, v in record.items() if k not in ('refresh_token', 'account', 'account_name', 'signed_in_at', 'last_test', 'device_code', 'sign_in_expires')})
    return public_view(_read(user_id, identifier))


def _access_token(user_id, record, scope):
    """Exchange the stored refresh token for a short-lived access token and keep the rotated refresh token."""
    if not record.get('refresh_token'):
        raise ValueError('Microsoft account not signed in for connection ' + record['id'] + ': sign in again from Connections')
    status, payload = _post(_endpoint(record, 'token'), {
        'grant_type': 'refresh_token', 'client_id': record['client_id'], 'refresh_token': record['refresh_token'], 'scope': scope + ' offline_access'})
    if status != 200 or not payload.get('access_token'):
        raise ValueError('Microsoft sign-in expired or was revoked for connection ' + record['id'] + ': sign in again from Connections (' + _error(payload, status) + ')')
    if payload.get('refresh_token') and payload['refresh_token'] != record['refresh_token']:
        _write(user_id, {**record, 'refresh_token': payload['refresh_token']})
    expires = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + int(payload.get('expires_in', 3600))))
    return payload['access_token'], expires


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
    if kind == 'entra' and entra_mode(record) == 'user':
        # Only short-lived access tokens leave the gateway; the refresh token never reaches a worker.
        token, expires = _access_token(user_id, record, SQL_SCOPES[record['cloud']])
        value = {'kind': 'entra', 'mode': 'user', 'account': record.get('account', ''), 'cloud': record['cloud'],
                 'access_token': token, 'expires_at': expires}
        if record['cloud'] == 'public':
            try:
                value['fabric_access_token'], value['fabric_expires_at'] = _access_token(user_id, _read(user_id, record['id']), FABRIC_SCOPE)
            except ValueError:
                pass  # Fabric REST may not be consented for this client; SQL access remains available
        return value
    if kind == 'entra':
        return {'kind': 'entra', 'tenant_id': record['tenant_id'], 'client_id': record['client_id'], 'client_secret': record['client_secret'],
                'authority_host': AUTHORITIES[record['cloud']], 'cloud': record['cloud']}
    host, port, database = record['host'], record['port'], record['database']
    base = {'kind': kind, 'host': host, 'port': port, 'database': database, 'read_only': record['read_only']}
    if record.get('authentication') == 'entra':
        entra = _read(user_id, record['entra_connection'])
        if entra_mode(entra) == 'user':
            token, expires = _access_token(user_id, entra, SQL_SCOPES[entra['cloud']])
            # go-mssqldb takes a ready access token in the password field with this fedauth value.
            return {**base, 'authentication': 'entra', 'account': entra.get('account', ''), 'expires_at': expires,
                    'usql_url': f'azuresql://{quote(entra.get("account") or "user", safe="")}:{quote(token, safe="")}@{host}:{port}'
                                f'?database={quote(database)}&fedauth=ActiveDirectoryServicePrincipalAccessToken&encrypt=true'}
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
    def __init__(self, workspace, destination, role=None):
        self.directory = None
        self.public = []
        self.domains = []
        from .project_store import locked, load
        with locked(workspace) as directory:
            value = load(directory, workspace) or {}
        binding = value.get('connections') or {}
        granted = list(binding.get('ids') or [])
        # Compiled roles receive only the subset they actually need. No access by default.
        requested = role.get('connections', []) if role else []
        if set(requested)-set(granted):
            raise ValueError('Role requests connections not authorized by the project owner')
        wanted = [c for c in granted if c in requested]
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
