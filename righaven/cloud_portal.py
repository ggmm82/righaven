"""Dual-Mode Architecture ('n8n-Style' Community Self-Hosted + Multi-Tenant Cloud Portal)."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from pathlib import Path

from . import state
from .i18n import normalize_locale

VALID_EDITIONS = ('community', 'cloud')
USER_ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{2,47}\Z')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+\Z')


def current_edition() -> str:
    raw = os.getenv('RIGHAVEN_EDITION', 'community').strip().lower()
    return raw if raw in VALID_EDITIONS else 'community'


def edition_info() -> dict:
    edition = current_edition()
    return {
        'edition': edition,
        'is_cloud': edition == 'cloud',
        'is_community': edition == 'community',
        'features': {
            'self_hosted_docker_compose': True,
            'community_gallery_sync': 'bidirectional' if edition == 'cloud' else 'read_or_bidirectional',
            'multi_tenant_workspaces': edition == 'cloud',
            'cloud_oauth_signup': edition == 'cloud',
            'encrypted_api_key_vault': True,
            'resource_quotas': edition == 'cloud',
            'community_creator_publishing': True,
        },
    }


def _users_store_path() -> Path:
    return state.STATE / 'cloud-tenants.json'


def _vault_store_path(user_id: str) -> Path:
    return state.STATE / 'cloud-vault' / f'{user_id}.enc.json'


def _quotas_store_path(user_id: str) -> Path:
    return state.STATE / 'cloud-quotas' / f'{user_id}.json'


def tenant_workspace_root(base_root: str | Path | None = None) -> Path:
    root = Path(base_root or os.getenv('RIGHAVEN_WORKSPACE_ROOT', '/mnt/user-data'))
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        root = state.STATE / 'user-data'
        root.mkdir(parents=True, exist_ok=True)
    return root / 'tenants'


def ensure_tenant_workspace(user_id: str, base_root: str | Path | None = None) -> Path:
    if not USER_ID_RE.fullmatch(user_id):
        raise ValueError('Invalid tenant user_id')
    ws = tenant_workspace_root(base_root) / user_id
    ws.mkdir(parents=True, exist_ok=True, mode=0o700)
    (ws / '.righaven-project').mkdir(exist_ok=True, mode=0o700)
    (ws / '.righaven-jobs').mkdir(exist_ok=True, mode=0o700)
    (ws / 'outputs/workspace').mkdir(parents=True, exist_ok=True, mode=0o755)
    return ws


def _secret_key() -> bytes:
    raw = os.getenv('RIGHAVEN_CREDENTIALS_KEY') or os.getenv('RIGHAVEN_PASSWORD') or 'righaven-default-signing-secret-key'
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120_000)
    return f'{salt}${dk.hex()}'


def _verify_password(password: str, stored: str) -> bool:
    if '$' not in stored:
        return False
    salt, _ = stored.split('$', 1)
    return hmac.compare_digest(_hash_password(password, salt), stored)


def issue_jwt(user_id: str, email: str, locale: str = 'en', expires_hours: int = 24) -> str:
    header = base64.urlsafe_b64encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()).rstrip(b'=').decode()
    exp = int((datetime.now(timezone.utc) + timedelta(hours=expires_hours)).timestamp())
    payload_dict = {
        'sub': user_id,
        'email': email,
        'locale': normalize_locale(locale),
        'edition': current_edition(),
        'exp': exp,
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b'=').decode()
    signing_input = f'{header}.{payload}'.encode()
    sig = base64.urlsafe_b64encode(hmac.new(_secret_key(), signing_input, hashlib.sha256).digest()).rstrip(b'=').decode()
    return f'{header}.{payload}.{sig}'


def verify_jwt(token: str) -> dict:
    parts = (token or '').split('.')
    if len(parts) != 3:
        raise ValueError('Invalid JWT format')
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f'{header_b64}.{payload_b64}'.encode()
    expected_sig = base64.urlsafe_b64encode(hmac.new(_secret_key(), signing_input, hashlib.sha256).digest()).rstrip(b'=').decode()
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise ValueError('Invalid JWT signature')
    pad = '=' * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad).decode())
    if payload.get('exp', 0) < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError('JWT token expired')
    return payload


def signup_user(username: str, email: str, password: str, *, locale: str = 'en', base_root: str | Path | None = None) -> dict:
    user_id = username.strip().lower()
    email = email.strip().lower()
    if not USER_ID_RE.fullmatch(user_id):
        raise ValueError('Username must be 3-48 lowercase alphanumeric characters, hyphens, or underscores')
    if not EMAIL_RE.fullmatch(email):
        raise ValueError('Invalid email address')
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    norm_locale = normalize_locale(locale)
    with state.LOCK:
        path = _users_store_path()
        users = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        if user_id in users or any(u.get('email') == email for u in users.values()):
            raise ValueError('User or email already registered')
        ws = ensure_tenant_workspace(user_id, base_root)
        record = {
            'user_id': user_id,
            'email': email,
            'password_hash': _hash_password(password),
            'locale': norm_locale,
            'workspace_path': f'/mnt/user-data/tenants/{user_id}',
            'physical_workspace_path': str(ws),
            'onboarding_completed': False,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        users[user_id] = record
        state.atomic_json(path, users)
        _init_quotas(user_id)
    token = issue_jwt(user_id, email, locale=norm_locale)
    return {
        'ok': True,
        'token': token,
        'user': _public_user(record),
        'quotas': get_tenant_quotas(user_id),
    }


def login_user(identifier: str, password: str) -> dict:
    ident = identifier.strip().lower()
    path = _users_store_path()
    users = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    record = users.get(ident) or next((u for u in users.values() if u.get('email') == ident), None)
    if not record or not _verify_password(password, record.get('password_hash', '')):
        raise ValueError('Invalid credentials')
    token = issue_jwt(record['user_id'], record['email'], locale=record.get('locale', 'en'))
    return {
        'ok': True,
        'token': token,
        'user': _public_user(record),
        'quotas': get_tenant_quotas(record['user_id']),
    }


def oauth_login(provider: str, external_username: str, email: str, *, locale: str = 'en', base_root: str | Path | None = None) -> dict:
    if provider not in ('github', 'google'):
        raise ValueError('Unsupported OAuth2 provider; use github or google')
    user_id = re.sub(r'[^a-z0-9_-]', '-', external_username.strip().lower()).strip('-')[:40]
    if len(user_id) < 3:
        user_id = f'{provider}-{uuid.uuid4().hex[:8]}'
    email = email.strip().lower()
    with state.LOCK:
        path = _users_store_path()
        users = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        record = users.get(user_id)
        if not record:
            ws = ensure_tenant_workspace(user_id, base_root)
            record = {
                'user_id': user_id,
                'email': email,
                'oauth_provider': provider,
                'password_hash': '',
                'locale': normalize_locale(locale),
                'workspace_path': f'/mnt/user-data/tenants/{user_id}',
                'physical_workspace_path': str(ws),
                'onboarding_completed': False,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            users[user_id] = record
            state.atomic_json(path, users)
            _init_quotas(user_id)
    token = issue_jwt(record['user_id'], record['email'], locale=record.get('locale', 'en'))
    return {
        'ok': True,
        'provider': provider,
        'token': token,
        'user': _public_user(record),
        'quotas': get_tenant_quotas(record['user_id']),
    }


def recover_password(email: str, new_password: str | None = None) -> dict:
    email = email.strip().lower()
    with state.LOCK:
        path = _users_store_path()
        users = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        record = next((u for u in users.values() if u.get('email') == email), None)
        if not record:
            raise KeyError('Account email not found')
        recovery_token = secrets.token_urlsafe(24)
        record['recovery_token_sha256'] = hashlib.sha256(recovery_token.encode()).hexdigest()
        if new_password:
            if len(new_password) < 8:
                raise ValueError('New password must be at least 8 characters')
            record['password_hash'] = _hash_password(new_password)
        state.atomic_json(path, users)
    return {'ok': True, 'email': email, 'recovery_token': recovery_token, 'password_updated': bool(new_password)}


def complete_onboarding(user_id: str, *, locale: str = 'en', default_engine: str = 'deepseek', starter_pack_id: str = 'env-architecture-modeling-rig') -> dict:
    with state.LOCK:
        path = _users_store_path()
        users = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        if user_id not in users:
            raise KeyError('User not found')
        users[user_id]['locale'] = normalize_locale(locale)
        users[user_id]['default_engine'] = default_engine
        users[user_id]['starter_pack_id'] = starter_pack_id
        users[user_id]['onboarding_completed'] = True
        state.atomic_json(path, users)
    from . import gallery
    gallery.activate_pack(starter_pack_id, user_id=user_id, locale=locale)
    return {'ok': True, 'user': _public_user(users[user_id])}


def _public_user(record: dict) -> dict:
    return {
        k: record.get(k)
        for k in ('user_id', 'email', 'locale', 'workspace_path', 'onboarding_completed', 'oauth_provider', 'default_engine', 'starter_pack_id', 'created_at')
        if k in record
    }


def get_user(user_id: str) -> dict:
    path = _users_store_path()
    users = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if user_id not in users:
        raise KeyError('Tenant user not found')
    return _public_user(users[user_id])


# --- Encrypted LLM API Key Vault ---
def _encrypt_secret(plaintext: str) -> dict:
    nonce = secrets.token_bytes(16)
    raw = plaintext.encode('utf-8')
    stream = b''.join(
        hashlib.sha256(_secret_key() + nonce + i.to_bytes(4, 'big')).digest()
        for i in range((len(raw) // 32) + 1)
    )[:len(raw)]
    ciphertext = bytes(a ^ b for a, b in zip(raw, stream))
    mac = hmac.new(_secret_key(), nonce + ciphertext, hashlib.sha256).hexdigest()
    return {
        'nonce': base64.b64encode(nonce).decode(),
        'ciphertext': base64.b64encode(ciphertext).decode(),
        'mac': mac,
    }


def _decrypt_secret(envelope: dict) -> str:
    nonce = base64.b64decode(envelope['nonce'])
    ciphertext = base64.b64decode(envelope['ciphertext'])
    expected_mac = hmac.new(_secret_key(), nonce + ciphertext, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(envelope.get('mac', ''), expected_mac):
        raise ValueError('Vault integrity check failed')
    stream = b''.join(
        hashlib.sha256(_secret_key() + nonce + i.to_bytes(4, 'big')).digest()
        for i in range((len(ciphertext) // 32) + 1)
    )[:len(ciphertext)]
    return bytes(a ^ b for a, b in zip(ciphertext, stream)).decode('utf-8')


def store_vault_key(user_id: str, provider: str, api_key: str) -> dict:
    if provider not in ('codex', 'gemini', 'deepseek', 'openai'):
        raise ValueError('Unsupported provider for Vault')
    if not api_key or len(api_key.strip()) < 6:
        raise ValueError('API key cannot be empty')
    with state.LOCK:
        path = _vault_store_path(user_id)
        vault = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        vault[provider] = {
            'provider': provider,
            'encrypted': _encrypt_secret(api_key.strip()),
            'masked_preview': api_key.strip()[:3] + '...' + api_key.strip()[-2:],
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        state.atomic_json(path, vault)
    return list_vault_keys(user_id)


def list_vault_keys(user_id: str) -> dict:
    path = _vault_store_path(user_id)
    vault = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    return {
        'user_id': user_id,
        'providers': {
            prov: {
                'configured': True,
                'masked_preview': entry.get('masked_preview', '***'),
                'updated_at': entry.get('updated_at', ''),
            }
            for prov, entry in vault.items()
        },
    }


def delete_vault_key(user_id: str, provider: str) -> dict:
    with state.LOCK:
        path = _vault_store_path(user_id)
        vault = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        vault.pop(provider, None)
        state.atomic_json(path, vault)
    return list_vault_keys(user_id)


# --- Resource Quotas & Job History ---
def _init_quotas(user_id: str) -> dict:
    path = _quotas_store_path(user_id)
    if not path.is_file():
        default_q = {
            'user_id': user_id,
            'plan': 'cloud-pro',
            'sandbox_minutes_used': 0.0,
            'sandbox_minutes_limit': 600.0,
            'storage_bytes_used': 0,
            'storage_bytes_limit': 10 * 1024**3,
            'tokens_used': 0,
            'tokens_limit': 5_000_000,
            'jobs_history': [],
        }
        state.atomic_json(path, default_q)
    return json.loads(path.read_text(encoding='utf-8'))


def get_tenant_quotas(user_id: str) -> dict:
    return _init_quotas(user_id)


def record_tenant_usage(user_id: str, *, sandbox_minutes: float = 0.0, storage_bytes: int = 0, tokens: int = 0, job_id: str | None = None) -> dict:
    with state.LOCK:
        quotas = _init_quotas(user_id)
        quotas['sandbox_minutes_used'] = round(quotas['sandbox_minutes_used'] + float(sandbox_minutes), 2)
        quotas['storage_bytes_used'] = max(0, int(quotas['storage_bytes_used'] + int(storage_bytes)))
        quotas['tokens_used'] = max(0, int(quotas['tokens_used'] + int(tokens)))
        if job_id:
            quotas.setdefault('jobs_history', []).append({
                'job_id': job_id,
                'sandbox_minutes': sandbox_minutes,
                'tokens': tokens,
                'at': datetime.now(timezone.utc).isoformat(),
            })
        quotas['quota_exceeded'] = (
            quotas['sandbox_minutes_used'] > quotas['sandbox_minutes_limit']
            or quotas['storage_bytes_used'] > quotas['storage_bytes_limit']
            or quotas['tokens_used'] > quotas['tokens_limit']
        )
        state.atomic_json(_quotas_store_path(user_id), quotas)
    return quotas


def get_creator_profile(username: str, locale: str = 'en') -> dict:
    from . import gallery
    all_packs = gallery.list_packs(locale=locale)['packs']
    authored = [p for p in all_packs if p.get('author', '').lower() == username.lower()]
    return {
        'username': username,
        'published_count': len(authored),
        'total_stars': sum(int(p.get('stars', 0)) for p in authored),
        'total_forks': sum(int(p.get('forks', 0)) for p in authored),
        'packs': authored,
    }
