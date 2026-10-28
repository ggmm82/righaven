"""Private, single-owner admin UI behind the deployment's HTTP authentication."""
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, SecretStr
if not hasattr(BaseModel, "model_dump"):
    BaseModel.model_dump = lambda self, **kw: self.dict(**kw)

from . import login
from .state import applications, catalog, update_agent, connection_status, available_skills, team, effective_agent

router = APIRouter(prefix='/harness', tags=['RigHaven'])


def same_origin(request):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Richiesta da un altro sito')
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403, 'Origine non consentita')


@router.get('')
@router.get('/')
def page():
    return FileResponse(Path(__file__).parent / 'index.html')


@router.get('/api/catalog')
def get_catalog():
    from .capability_policy import current_policy, public
    policy = current_policy()
    from .state import custom_connection_path
    import json
    custom = json.loads(custom_connection_path().read_text()) if connection_status('openai') else {}
    agents = catalog()
    agents = {name: {**config, 'enabled': name in policy['allowed']} for name, config in agents.items()}
    effective = {a['id']: {**effective_agent(a['id']), 'enabled': a['id'] in policy['allowed']} for a in applications()}
    return {'team': team(), 'capability_policy': public(policy), 'profiles': {'coordinator': team(), 'squad': team('squad')}, 'effective_agents': effective, 'agents': agents, 'skills': available_skills(), 'applications': [
        {k: a[k] for k in ('id', 'name', 'role', 'description', 'version')}
        for a in applications()], 'connections': {
            engine: {'credentials_present': connection_status(engine), **(
                {k: custom.get(k, '') for k in ('base_url', 'connection_id')} if engine == 'openai' else {})}
            for engine in ('codex', 'gemini', 'deepseek', 'openai')}}


class AgentConfig(BaseModel):
    engine: str = Field(default='inherit', pattern='^(inherit|codex|gemini|deepseek|openai)$')
    model: str = Field(default='', max_length=200)
    instructions: str = Field(default='', max_length=20000)
    enabled: bool | None = None
    skills: list[str] = Field(default_factory=list)


@router.put('/api/agents/{identifier}')
async def save_agent(identifier: str, value: AgentConfig, request: Request):
    same_origin(request)
    try:
        from .capability_policy import current_policy
        policy = current_policy()
        if policy['source'] == 'righaven_core' and value.enabled is not None:
            # Compatibility endpoint delegates the write and authorization to
            # RigHaven itself. There is no separate RigHaven enablement state.
            from app.gateway.routers.skills import update_skill, SkillUpdateRequest
            from righaven_core.config import get_app_config
            await update_skill('skill-' + identifier, SkillUpdateRequest(enabled=value.enabled), request, get_app_config())
        payload = value.model_dump()
        # Preserve the original global legacy import baseline. A user's native
        # toggle must not change another user's future migration defaults.
        payload['enabled'] = catalog().get(identifier, {}).get('enabled', True) if policy['source'] == 'righaven_core' else (
            value.enabled if value.enabled is not None else identifier in policy['allowed'])
        saved = update_agent(identifier, payload)
        if policy['source'] == 'righaven_core':
            saved = {**saved, 'enabled': identifier in current_policy()['allowed']}
        return saved
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


@router.post('/api/login/{engine}')
def begin_login(engine: str, request: Request):
    same_origin(request)
    if engine not in ('codex', 'gemini'):
        raise HTTPException(400, 'Motore sconosciuto')
    try:
        return login.start(engine)
    except (RuntimeError, OSError, ValueError) as error:
        raise HTTPException(409, str(error)) from None


@router.get('/api/login-session/{identifier}')
def read_login(identifier: str):
    session = login.SESSIONS.get(identifier)
    if not session:
        raise HTTPException(404, 'Sessione non trovata')
    return session.public()


class LoginInput(BaseModel):
    text: str = Field(max_length=4096)


@router.post('/api/login-session/{identifier}/input')
def login_input(identifier: str, value: LoginInput, request: Request):
    same_origin(request)
    session = login.SESSIONS.get(identifier)
    if not session:
        raise HTTPException(404, 'Sessione non trovata')
    try:
        session.write(value.text)
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from None
    return {'ok': True}


@router.delete('/api/login-session/{identifier}')
def cancel_login(identifier: str, request: Request):
    same_origin(request)
    session = login.SESSIONS.get(identifier)
    if session:
        session.cancel()
    return {'ok': True}


class TeamConfig(BaseModel):
    engine: str = Field(pattern='^(codex|deepseek|gemini|openai)$')
    model: str = Field(default='', max_length=200)
    api_key: SecretStr | None = None
    scope: str = Field(default='both', pattern='^(both|coordinator|squad)$')
    base_url: str | None = Field(default=None, max_length=2000)
    connection_id: str | None = Field(default=None, pattern='^[0-9a-f]{32}$')


def custom_credentials(value):
    import json
    from .state import custom_connection_path
    from .openai_compatible import endpoint, validate_key
    path = custom_connection_path(value.connection_id)
    previous = json.loads(path.read_text()) if path.is_file() else {}
    base_url = endpoint(value.base_url or previous.get('base_url', ''))
    key = value.api_key.get_secret_value().strip() if value.api_key else None
    if not key:
        if base_url != previous.get('base_url'):
            raise ValueError('Se cambi endpoint, inserisci nuovamente la chiave API')
        key = previous.get('api_key')
    return base_url, validate_key(key), previous


@router.post('/api/team/models')
def preview_custom_models(value: TeamConfig, request: Request):
    same_origin(request)
    from .openai_compatible import models
    try:
        if value.engine != 'openai':
            raise ValueError('Usa questa verifica per un endpoint OpenAI compatibile')
        base_url, key, _ = custom_credentials(value)
        return {'models': models(base_url, key)}
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except RuntimeError:
        raise HTTPException(502, 'Elenco modelli non disponibile: inserisci l’ID manualmente.') from None


def validated_deepseek(key, model):
    from .deepseek import models
    if not key or len(key) > 512 or any(ord(c) < 33 for c in key):
        raise ValueError('Chiave DeepSeek non valida')
    available = models(key)
    chosen = model.strip() or next((m for m in ('deepseek-chat', 'deepseek-flash') if m in available), available[0] if available else '')
    if not chosen or chosen not in available:
        raise ValueError('Seleziona un modello DeepSeek disponibile')
    return chosen, available


@router.get('/api/team/models')
def team_models(engine: str = 'deepseek', connection_id: str | None = None):
    import json
    from .state import credential_dir
    from .deepseek import models
    if engine == 'openai':
        from .state import custom_connection_path
        from .openai_compatible import models as compatible_models
        try:
            path = custom_connection_path(connection_id)
            if not path.is_file():
                raise ValueError('Collega prima l’endpoint OpenAI compatibile')
            connection = json.loads(path.read_text())
            return {'models': compatible_models(connection['base_url'], connection['api_key'])}
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        except RuntimeError as error:
            raise HTTPException(502, str(error)) from None
    if engine in ('codex', 'gemini'):
        if not connection_status(engine):
            raise HTTPException(400, 'Collega prima ' + ('Antigravity' if engine == 'gemini' else 'Codex'))
        from .docker_runtime import codex_models, antigravity_models
        try:
            available = antigravity_models() if engine == 'gemini' else codex_models()
        except (ValueError, RuntimeError) as error:
            raise HTTPException(502, str(error)) from None
        return {'models': (['auto'] if engine == 'gemini' else []) + [item['id'] for item in available], 'details': ([{'id': 'auto', 'label': 'Automatico della CLI'}] if engine == 'gemini' else []) + available}
    if engine != 'deepseek':
        raise HTTPException(400, 'Elenco automatico disponibile per DeepSeek')
    path = credential_dir('deepseek') / 'api.json'
    if not path.is_file():
        raise HTTPException(400, 'Collega prima DeepSeek')
    try:
        available = models(json.loads(path.read_text())['api_key'])
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from None
    return {'models': available}


@router.put('/api/team')
def save_team(value: TeamConfig, request: Request):
    same_origin(request)
    import json
    from .state import credential_dir
    from .bootstrap import configure_team
    try:
        key = value.api_key.get_secret_value().strip() if value.api_key else None
        available = []
        chosen = value.model.strip()
        connection_id, base_url = value.connection_id, value.base_url
        token_limit_param = 'max_tokens'
        tool_choice = 'specified'
        reasoning = False
        vision = False
        if value.engine == 'openai':
            from .openai_compatible import validate
            base_url, key, previous = custom_credentials(value)
            base_url, chosen, available, token_limit_param, tool_choice, reasoning, vision = validate(base_url, key, chosen)
            connection_id = previous.get('connection_id') if (base_url, key, token_limit_param, tool_choice, reasoning, vision) == (previous.get('base_url'), previous.get('api_key'), previous.get('token_limit_param','max_tokens'), previous.get('tool_choice','specified'), previous.get('reasoning',False), previous.get('vision',False)) else None
        elif value.engine == 'deepseek':
            if not key:
                path = credential_dir('deepseek') / 'api.json'
                if not path.is_file():
                    raise ValueError('Inserisci la chiave DeepSeek per attivare la squadra')
                key = json.loads(path.read_text())['api_key']
            chosen, available = validated_deepseek(key, chosen)
        elif not connection_status(value.engine):
            raise ValueError('Collega prima il tuo account ' + ('Antigravity' if value.engine == 'gemini' else 'Codex'))
        else:
            if value.engine == 'codex':
                from .docker_runtime import codex_models
                entries = codex_models()
                # Labels are for humans; native API requests always use catalog IDs.
                matches = [item['id'] for item in entries if item['label'] == chosen]
                if chosen and len(matches) == 1:
                    chosen = matches[0]
                if not chosen:
                    chosen = next((item['id'] for item in entries if item['default']), entries[0]['id'] if entries else '')
                if chosen not in [item['id'] for item in entries]:
                    raise ValueError('Scegli un modello dall’elenco del tuo account Codex')
                available = [item['id'] for item in entries]
            else:
                from .docker_runtime import antigravity_models
                entries = antigravity_models()
                available = ['auto', *[item['id'] for item in entries]]
                chosen = chosen or 'auto'
                if chosen not in available:
                    raise ValueError('Scegli un modello dall’elenco del tuo account Antigravity')
        configure_team(value.engine, chosen, key if value.engine in ('deepseek', 'openai') else None,
                       scope=value.scope, base_url=base_url, connection_id=connection_id, token_limit_param=token_limit_param, tool_choice=tool_choice, reasoning=reasoning, vision=vision)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from None
    return {'ok': True, 'team': team(), 'profiles': {'coordinator': team(), 'squad': team('squad')},
            'applied_to': value.scope, 'models': available}


class CoordinatorConfig(BaseModel):
    model: str = Field(min_length=1, max_length=200)


@router.put('/api/coordinator', deprecated=True)
def set_coordinator(value: CoordinatorConfig, request: Request):
    # Compatibility endpoint retains its historical shared-profile behavior.
    profile = team()
    result = save_team(TeamConfig(engine=profile['engine'], model=value.model,
        connection_id=profile.get('connection_id'), base_url=profile.get('base_url')), request)
    return {**result, 'model': result['team']['model']}


class DeepSeekConfig(BaseModel):
    api_key: SecretStr
    model: str = Field(default='', max_length=200)


@router.put('/api/providers/deepseek')
def connect_deepseek(value: DeepSeekConfig, request: Request):
    same_origin(request)
    result = save_team(TeamConfig(engine='deepseek', model=value.model, api_key=value.api_key), request)
    return {'ok': True, 'model': result['team']['model'], 'models': result['models']}


class RuntimeConfig(BaseModel):
    mode: str = Field(default='auto', pattern='^(auto|manual)$')
    cpus: float = Field(default=1.5, ge=.5, le=32)
    memory_mib: int = Field(default=1536, ge=512, le=65536)
    model_wait_seconds: int = Field(default=0, ge=0, le=1500)
    max_workers: int = Field(default=2,ge=1,le=8)


@router.get('/api/runtime')
def runtime_settings():
    from .runtime_settings import read
    return read()


@router.put('/api/runtime')
def save_runtime(value: RuntimeConfig, request: Request):
    same_origin(request)
    from .runtime_settings import save
    try:
        return save(value.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
