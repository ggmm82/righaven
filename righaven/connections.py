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
EMAIL = re.compile(r'[^@\s]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})+\Z')
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
    if record['kind'] == 'entra' or record.get('authentication') == 'microsoft':
        value['signed_in'] = bool(record.get('refresh_token'))
    value['tools'] = usable_tools(record)
    return value


def entra_mode(record):
    return record.get('mode') or 'application'  # connections saved before personal sign-in were applications


def usable_tools(record):
    if record['kind'] == 'entra':
        return []
    if record['kind'] == 'sqlserver' and record.get('authentication') in ('entra', 'microsoft'):
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
    body = {**body, **address(kind, body.get('host'), body)}
    port = body.get('port') or DEFAULT_PORTS[kind]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Porta tra 1 e 65535')
    authentication = body.get('authentication', 'password') if kind == 'sqlserver' else 'password'
    if authentication not in ('password', 'entra', 'microsoft'):
        raise ValueError('Autenticazione SQL Server: password, microsoft o entra')
    record.update(host=_text(body.get('host'), 'host', HOST, 253), port=port,
                  # With a Microsoft account the database can be chosen from the list after signing in.
                  database=_text(body.get('database'), 'database', NAME, 128, required=authentication != 'microsoft'),
                  read_only=body.get('read_only') is True, tls=body.get('tls', True) is not False)
    record['authentication'] = authentication
    if authentication == 'entra':
        record['entra_connection'] = _text(body.get('entra_connection'), 'connessione Entra', CONNECTION_ID, 40)
        return record
    if authentication == 'microsoft':
        # The user's own work or school account, signed in on Microsoft's page with MFA.
        record.update(username=_text(body.get('username'), 'utente (email dell’account Microsoft)', EMAIL, 254),
                      tenant_id=_text(body.get('tenant_id') or 'organizations', 'tenant (ID o dominio)', TENANT, 120),
                      client_id=_text(body.get('client_id') or PUBLIC_CLIENT, 'ID applicazione (client)', GUID, 36),
                      cloud=body.get('cloud', 'public'))
        if record['cloud'] not in AUTHORITIES:
            raise ValueError('Cloud Microsoft tra ' + ', '.join(AUTHORITIES))
        if previous and previous.get('authentication') == 'microsoft' and all(
                previous.get(k) == record[k] for k in ('username', 'tenant_id', 'client_id', 'cloud')):
            record.update({k: previous[k] for k in ('refresh_token', 'account', 'account_name', 'signed_in_at') if previous.get(k)})
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
        if record.get('authentication') == 'microsoft':
            if not record.get('refresh_token'):
                result = {'ok': False, 'detail': 'Sign in with Microsoft first'}
            else:
                _access_token(user_id, record, SQL_SCOPES[record['cloud']])
                addresses = _addresses(record['host'], record['port'])
                with socket.create_connection((addresses[0], record['port']), timeout=6):
                    pass
                result = {'ok': True, 'detail': record['host'] + ':' + str(record['port']) + ' raggiungibile; token ottenuto per ' + str(record.get('account') or record['username'])}
                record = _read(user_id, identifier)
        elif record['kind'] == 'entra' and entra_mode(record) == 'user':
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


# --- Addresses pasted as URL or connection string ----------------------------------------

def address(kind, text, body=None):
    """Host, port, database and user from what users paste: ADO/ODBC/JDBC strings, URLs or tcp:host,port."""
    from urllib.parse import urlsplit, parse_qs, unquote
    if not isinstance(text, str) or HOST.fullmatch(text.strip()):
        return {}
    text = text.strip()
    found = {}
    if '=' in text and ';' in text and not text.lower().startswith('jdbc:'):
        pairs = {k.strip().lower(): v.strip() for k, _, v in (p.partition('=') for p in text.split(';') if '=' in p)}
        server = next((pairs[k] for k in ('server', 'data source', 'address', 'addr', 'host') if pairs.get(k)), '')
        database = next((pairs[k] for k in ('database', 'initial catalog', 'dbname') if pairs.get(k)), '')
        user = next((pairs[k] for k in ('user id', 'uid', 'user', 'username') if pairs.get(k)), '')
        found.update(_host_port(server), **({'database': database} if database else {}), **({'username': user} if user else {}))
    elif text.lower().startswith('jdbc:sqlserver://'):
        head, *options = text[len('jdbc:sqlserver://'):].split(';')
        pairs = {k.strip().lower(): v.strip() for k, _, v in (p.partition('=') for p in options if '=' in p)}
        found.update(_host_port(head))
        if pairs.get('databasename') or pairs.get('database'):
            found['database'] = pairs.get('databasename') or pairs.get('database')
        if pairs.get('user'):
            found['username'] = pairs['user']
    elif '://' in text:
        parts = urlsplit(text[5:] if text.lower().startswith('jdbc:') else text)
        query = {k.lower(): v[0] for k, v in parse_qs(parts.query).items()}
        found.update({'host': parts.hostname or ''}, **({'port': parts.port} if parts.port else {}))
        database = query.get('database') or query.get('databasename') or unquote(parts.path.strip('/').split('/')[0])
        if database:
            found['database'] = database
        if parts.username:
            found['username'] = unquote(parts.username)
    else:
        found.update(_host_port(text))
    if not found.get('host') or not HOST.fullmatch(found['host']):
        raise ValueError('Server non riconosciuto: incolla il nome del server, un URL o una stringa di connessione')
    body = body or {}
    # Explicit form fields win over values found in the pasted text, except the default port.
    return {k: v for k, v in found.items() if k == 'host' or not body.get(k) or (k == 'port' and body.get(k) == DEFAULT_PORTS.get(kind))}


def _host_port(server):
    server = server.strip()
    if server.lower().startswith('tcp:'):
        server = server[4:]
    if '\\' in server:
        raise ValueError('Named SQL Server instances are not supported: use the server name and its TCP port')
    host, separator, port = server.replace(',', ':').rpartition(':') if (',' in server or server.count(':') == 1) else (server, '', '')
    if not separator:
        host = server
    try:
        return {'host': host.strip(), **({'port': int(port)} if port.strip() else {})}
    except ValueError:
        raise ValueError('Porta non valida: ' + port) from None


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
    if not ((record['kind'] == 'entra' and entra_mode(record) == 'user') or record.get('authentication') == 'microsoft'):
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
        if record.get('username') and account and account.lower() != record['username'].lower():
            _write(user_id, {k: v for k, v in record.items() if k not in ('device_code', 'sign_in_expires')})
            return {'status': 'failed', 'detail': 'Signed in as ' + account + ', but this connection is for ' + record['username'] + ': sign in again with that account'}
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


# --- Databases visible to a Microsoft account ----------------------------------------------
ARM_SCOPE = 'https://management.azure.com/.default'
ARM = 'https://management.azure.com'
FABRIC = 'https://api.fabric.microsoft.com/v1'
LIMIT = 25


def _get(url, token):
    import httpx
    try:
        response = httpx.get(url, headers={'Authorization': 'Bearer ' + token}, timeout=20)
    except httpx.HTTPError as error:
        raise ValueError('Microsoft service unreachable: ' + type(error).__name__) from None
    payload = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
    if response.status_code != 200:
        raise PermissionError(str((payload.get('error') or {}).get('code') if isinstance(payload.get('error'), dict) else payload.get('errorCode') or response.status_code))
    return payload


def _token_source(user_id, record):
    if record.get('authentication') == 'microsoft':
        return record
    if record.get('authentication') == 'entra':
        entra = _read(user_id, record['entra_connection'])
        if entra_mode(entra) == 'user':
            return entra
    raise ValueError('The database list uses your Microsoft account: choose authentication with a Microsoft account, or type the database name')


def databases(user_id, identifier):
    try:
        return _databases(user_id, identifier)
    except PermissionError as error:
        raise ValueError('Microsoft did not allow listing the databases (' + str(error) + '): type the database name') from None


def _databases(user_id, identifier):
    """Databases on this server that the signed-in account can see: Azure SQL through Azure Resource Manager, Fabric through its REST API."""
    record = _read(user_id, identifier)
    if record['kind'] != 'sqlserver':
        raise ValueError('The database list is available for SQL Server, Azure SQL and Fabric connections')
    source = _token_source(user_id, record)
    host = record['host'].lower()
    if '.fabric.microsoft.' in host or '.datawarehouse.' in host or '.pbidedicated.' in host:
        token, _ = _access_token(user_id, source, 'https://api.fabric.microsoft.com/.default')
        rows = []
        workspaces = _get(FABRIC + '/workspaces', token).get('value', [])[:LIMIT]
        for workspace in workspaces:
            for kind, path in (('Warehouse', 'warehouses'), ('Lakehouse', 'lakehouses'), ('SQL database', 'sqlDatabases')):
                try:
                    items = _get(f'{FABRIC}/workspaces/{workspace["id"]}/{path}', token).get('value', [])
                except PermissionError:
                    continue
                for item in items:
                    props = item.get('properties') or {}
                    endpoint = (props.get('sqlEndpointProperties') or {}).get('connectionString') or props.get('connectionString') or props.get('serverFqdn') or ''
                    if endpoint.split(',')[0].lower() == host:
                        rows.append({'name': props.get('databaseName') or item['displayName'], 'detail': kind + ' · ' + workspace.get('displayName', '')})
        return {'databases': rows, 'source': 'fabric'}
    if host.endswith(('.database.windows.net', '.database.usgovcloudapi.net', '.database.chinacloudapi.cn')):
        if source['cloud'] != 'public':
            raise ValueError('The database list is available on the global Microsoft cloud; type the database name')
        token, _ = _access_token(user_id, source, ARM_SCOPE)
        server = host.split('.')[0]
        rows = []
        try:
            subscriptions = _get(ARM + '/subscriptions?api-version=2022-12-01', token).get('value', [])[:LIMIT]
        except PermissionError as error:
            raise ValueError('Azure did not allow listing subscriptions (' + str(error) + '): type the database name') from None
        for subscription in subscriptions:
            url = (ARM + '/subscriptions/' + subscription['subscriptionId'] + "/resources?$filter=resourceType%20eq%20'Microsoft.Sql/servers/databases'"
                   + '&api-version=2021-04-01')
            try:
                resources = _get(url, token).get('value', [])
            except PermissionError:
                continue
            for resource in resources:
                owner, _, name = resource.get('name', '').partition('/')
                if owner.lower() == server and name and name.lower() != 'master':
                    rows.append({'name': name, 'detail': subscription.get('displayName', '') + ' · ' + resource.get('location', '')})
        return {'databases': rows, 'source': 'azure'}
    raise ValueError('The database list is available for Azure SQL and Microsoft Fabric servers; type the database name')


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
    if record.get('authentication') == 'microsoft':
        if not record.get('database'):
            raise ValueError('Choose the database of connection ' + record['id'] + ' in Connections')
        token, expires = _access_token(user_id, record, SQL_SCOPES[record['cloud']])
        return {**base, 'authentication': 'microsoft', 'account': record.get('account', ''), 'expires_at': expires,
                'usql_url': f'azuresql://{quote(record["username"], safe="")}:{quote(token, safe="")}@{host}:{port}'
                            f'?database={quote(database)}&fedauth=ActiveDirectoryServicePrincipalAccessToken&encrypt=true'}
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
            entra_cloud = record.get('cloud') if record['kind'] == 'entra' or record.get('authentication') == 'microsoft' else (_read(owner, record['entra_connection']).get('cloud') if record.get('authentication') == 'entra' else None)
            if entra_cloud:
                self.domains += ENTRA_DOMAINS[entra_cloud]

    def mount_arguments(self, mount):
        return ['--mount', mount(self.directory, MOUNT, True)] if self.directory else []

    def close(self):
        if self.directory:
            shutil.rmtree(self.directory, ignore_errors=True)
