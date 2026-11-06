"""RigHaven agents: PCs (and later phones) that put their Bluetooth, Wi-Fi, serial ports and home
network at the disposal of a RigHaven server, for example one on a VPS.

An agent belongs to one user. The user creates a short-lived pairing code in the web interface;
RigHaven.exe in agent mode redeems it once and receives its own token, which the server keeps
only as a hash. Every action asked to an agent is recorded in the owner's agent activity.
"""
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from .state import LOCK, STATE, atomic_json

FILE = 'agents.json'
ACTIVITY = 'agents-activity.jsonl'
CODE_SECONDS = 600
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no 0/O, 1/I
MAX_AGENTS = 10
MAX_PENDING_CODES = 5
MAX_FAILED_REDEEMS = 20  # per 10 minutes, all codes together: guessing a code is not practical
NAME = re.compile(r'[^\x00-\x1f\x7f]{1,60}\Z')
_failures = []


def _hash(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def _load():
    path = STATE / FILE
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        value = {}
    value.setdefault('agents', [])
    value.setdefault('codes', [])
    return value


def _save(value):
    now = time.time()
    value['codes'] = [c for c in value['codes'] if c['expires'] > now]
    atomic_json(STATE / FILE, value)


def public(agent):
    return {k: agent.get(k) for k in ('id', 'name', 'platform', 'version', 'created_at', 'last_seen', 'actions')}


def log(user, agent, action, detail='', status='done'):
    """The owner's record of what was asked to their agents (never secrets)."""
    line = json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'user': str(user), 'agent': agent,
                       'action': str(action)[:40], 'detail': str(detail)[:300], 'status': str(status)[:20]}, ensure_ascii=False)
    with LOCK:
        path = STATE / ACTIVITY
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as stream:
            stream.write(line + '\n')
        if path.stat().st_size > 4_000_000:
            lines = path.read_text().splitlines()[-10000:]
            path.write_text('\n'.join(lines) + '\n')


def activity(user, agent=None, limit=50):
    try:
        lines = (STATE / ACTIVITY).read_text().splitlines()
    except OSError:
        return []
    rows = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('user') == str(user) and (agent is None or row.get('agent') == agent):
            rows.append({k: v for k, v in row.items() if k != 'user'})
            if len(rows) >= limit:
                break
    return rows


def listing(user):
    with LOCK:
        return [public(a) for a in _load()['agents'] if a['user'] == str(user)]


def owned(user, identifier):
    """The agent if it belongs to this user, otherwise an error (an agent of another user does not exist for them)."""
    with LOCK:
        agent = next((a for a in _load()['agents'] if a['id'] == identifier and a['user'] == str(user)), None)
    if agent is None:
        raise ValueError('Agente non trovato')
    return public(agent)


def create_code(user, name):
    name = str(name or '').strip()
    if not NAME.fullmatch(name):
        raise ValueError('Dai un nome al PC da collegare (al massimo 60 caratteri)')
    with LOCK:
        value = _load()
        now = time.time()
        if sum(1 for a in value['agents'] if a['user'] == str(user)) >= MAX_AGENTS:
            raise ValueError('Al massimo 10 agenti per utente: revocane uno prima')
        if sum(1 for c in value['codes'] if c['user'] == str(user) and c['expires'] > now) >= MAX_PENDING_CODES:
            raise ValueError('Troppi codici in attesa: usa quelli già creati o aspetta qualche minuto')
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(10))
        value['codes'].append({'hash': _hash(code), 'user': str(user), 'name': name, 'expires': now + CODE_SECONDS})
        _save(value)
    log(user, '', 'pairing-code', name)
    return {'code': code[:5] + '-' + code[5:], 'expires_in': CODE_SECONDS}


def redeem(code, platform='', version=''):
    """Exchange a pairing code (once) for an agent token. The token is returned only here."""
    clean = re.sub(r'[^A-Z0-9]', '', str(code or '').upper())
    now = time.time()
    with LOCK:
        _failures[:] = [t for t in _failures if t > now - CODE_SECONDS]
        if len(_failures) >= MAX_FAILED_REDEEMS:
            raise PermissionError('Troppi codici sbagliati: riprova tra qualche minuto')
        value = _load()
        entry = next((c for c in value['codes'] if secrets.compare_digest(c['hash'], _hash(clean)) and c['expires'] > now), None)
        if entry is None:
            _failures.append(now)
            raise PermissionError('Codice di abbinamento non valido o scaduto: creane uno nuovo nella pagina Connessioni')
        value['codes'].remove(entry)
        token = 'rha_' + secrets.token_urlsafe(32)
        agent = {'id': 'ag_' + secrets.token_hex(6), 'user': entry['user'], 'name': entry['name'], 'token': _hash(token),
                 'platform': str(platform)[:20], 'version': str(version)[:40], 'actions': [],
                 'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'last_seen': None}
        value['agents'].append(agent)
        _save(value)
    log(entry['user'], agent['id'], 'paired', agent['name'] + ' · ' + agent['platform'])
    return {'agent': agent['id'], 'token': token, 'name': agent['name']}


def authenticate(token):
    """The agent of a token, or None. Tokens are compared by hash only."""
    if not isinstance(token, str) or not token.startswith('rha_') or len(token) > 100:
        return None
    digest = _hash(token)
    with LOCK:
        for agent in _load()['agents']:
            if secrets.compare_digest(agent['token'], digest):
                return dict(agent)
    return None


def seen(identifier, platform=None, version=None, actions=None):
    with LOCK:
        value = _load()
        for agent in value['agents']:
            if agent['id'] == identifier:
                agent['last_seen'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                if platform is not None:
                    agent['platform'] = str(platform)[:20]
                if version is not None:
                    agent['version'] = str(version)[:40]
                if actions is not None:
                    agent['actions'] = [str(a)[:30] for a in actions][:60]
                _save(value)
                return


def revoke(user, identifier):
    with LOCK:
        value = _load()
        agent = next((a for a in value['agents'] if a['id'] == identifier and a['user'] == str(user)), None)
        if agent is None:
            raise ValueError('Agente non trovato')
        value['agents'].remove(agent)
        _save(value)
    log(user, identifier, 'revoked', agent['name'])
    return {'revoked': identifier}


def folder(identifier):
    """Reports of one agent (Bluetooth, Wi-Fi, serial ports, last traffic recording), like the launcher's discovery folder."""
    if not re.fullmatch(r'ag_[0-9a-f]{12}', str(identifier)):
        raise ValueError('Agente non valido')
    path = Path(STATE) / 'agents' / identifier
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_address(request) -> str:
    """The address RigHaven Agent must use: the configured public URL (on Hostinger the HTTPS
    address Traefik serves), otherwise what the browser used, as forwarded by the proxy."""
    for name in ('RIGHAVEN_PUBLIC_URL', 'BETTER_AUTH_URL'):
        configured = os.getenv(name, '').strip().rstrip('/')
        if configured.startswith(('http://', 'https://')) and urlsplit(configured).hostname not in ('localhost', '127.0.0.1', '::1'):
            return configured
    scheme = request.headers.get('x-forwarded-proto', '').split(',')[0].strip() or request.url.scheme
    host = request.headers.get('x-forwarded-host', '').split(',')[0].strip() or request.headers.get('host') or request.url.netloc
    return f'{scheme}://{host}'
