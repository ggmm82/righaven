"""Private hosted model profiles and standard authenticated encryption."""
import json
import os
import uuid
from . import state


def cloud_user():
    if os.getenv('RIGHAVEN_EDITION', 'community') != 'cloud':
        return None
    from righaven_core.runtime.user_context import require_current_user
    return str(require_current_user().id)


def root():
    user = cloud_user()
    if user is None:
        return None
    from .organization_limits import snapshot
    directory = state.STATE / 'organizations' / snapshot(user)['id']
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def cipher():
    from cryptography.fernet import Fernet, MultiFernet
    keys = os.getenv('RIGHAVEN_CREDENTIALS_KEY', '').split(',')
    if not any(key.strip() for key in keys):
        raise ValueError('The operator must configure a persistent credentials encryption key')
    return MultiFernet([Fernet(key.strip().encode()) for key in keys if key.strip()])


def read_secret(path):
    value = json.loads(path.read_text())
    if isinstance(value, dict) and value.get('format') == 'fernet:v2':
        value = json.loads(cipher().decrypt(value['encrypted'].encode()).decode())
    if not isinstance(value, dict):
        raise ValueError('Invalid credentials')
    return value


class TenantBoundModel:
    """A model instance may never send another account's credentials."""
    def bind_tenant(self):
        object.__setattr__(self, '_righaven_tenant', cloud_user())

    def check_tenant(self):
        if getattr(self, '_righaven_tenant', None) != cloud_user():
            raise ValueError('Model instance belongs to a different hosted account')

    def _generate(self, *args, **kwargs):
        self.check_tenant()
        return super()._generate(*args, **kwargs)

    async def _agenerate(self, *args, **kwargs):
        self.check_tenant()
        return await super()._agenerate(*args, **kwargs)

    def _stream(self, *args, **kwargs):
        self.check_tenant()
        yield from super()._stream(*args, **kwargs)

    async def _astream(self, *args, **kwargs):
        self.check_tenant()
        async for item in super()._astream(*args, **kwargs):
            yield item


def profile(target):
    directory = root()
    if directory is None:
        return None
    path = directory / 'models.json'
    if not path.exists():
        raise ValueError('Configure your private model connection before starting a hosted job')
    profiles = json.loads(path.read_text())
    selected = profiles.get(target) or profiles.get('coordinator')
    if selected is None:
        raise ValueError('Configure your private coordinator model before starting a hosted job')
    return selected


def save(engine, model, api_key, *, scope='both', base_url=None):
    if engine not in ('deepseek', 'openai') or scope not in ('both','coordinator','squad'):
        raise ValueError('Hosted API profiles support DeepSeek and OpenAI-compatible endpoints')
    if not model or len(model)>200 or not api_key or len(api_key)>4096:
        raise ValueError('A model identifier and private API key are required')
    if engine == 'openai':
        from .openai_compatible import endpoint
        from urllib.parse import urlsplit
        base_url = endpoint(base_url)
        allowed = os.getenv('RIGHAVEN_ALLOWED_PROVIDER_HOSTS', 'api.openai.com,api.deepseek.com').split(',')
        if urlsplit(base_url).scheme != 'https' or urlsplit(base_url).hostname not in {host.strip() for host in allowed}:
            raise ValueError('This hosted provider endpoint has not been approved by the operator')
    directory = root()
    if directory is None:
        raise ValueError('Private hosted profiles require Cloud mode')
    identifier = uuid.uuid4().hex if engine == 'openai' else None
    path = state.custom_connection_path(identifier) if identifier else state.credential_dir(engine)/'api.json'
    secret = {'api_key':api_key, 'base_url':base_url, 'connection_id':identifier}
    encrypted = cipher().encrypt(json.dumps(secret).encode()).decode()
    state.atomic_json(path, {'format':'fernet:v2','encrypted':encrypted})
    value = {'engine':engine,'model':model,'connection_id':identifier}
    with state.LOCK:
        path = directory / 'models.json'
        profiles = json.loads(path.read_text()) if path.exists() else {}
        for target in ('coordinator','squad') if scope=='both' else (scope,):
            profiles[target] = value
        state.atomic_json(path, profiles)
    return value


def model_config(original, name):
    selected = profile('squad' if name == 'rh-squad' else 'coordinator')
    if selected is None:
        return original
    provider = {'deepseek':'righaven.deepseek_provider:HarnessDeepSeekChatModel',
                'openai':'righaven.openai_provider:HarnessCompatibleChatModel'}[selected['engine']]
    # A hosted profile must not inherit global credentials, headers, endpoint or
    # provider-specific reasoning kwargs from the operator's default model.
    return type(original)(name=original.name, use=provider, model=selected['model'],
        connection_id=selected.get('connection_id'), request_timeout=300)
