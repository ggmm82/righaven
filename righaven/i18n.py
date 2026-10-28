"""Native Internationalization (i18n) engine for RigHaven (English default, Italian preset)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_LOCALES = ('en', 'it')
DEFAULT_LOCALE = 'en'
_CACHE = {}


def load_dictionary(locale: str) -> dict:
    norm = normalize_locale(locale)
    if norm in _CACHE:
        return _CACHE[norm]
    for candidate in (
        ROOT / 'locales' / norm / 'common.json',
        ROOT / 'frontend/locales' / norm / 'common.json',
        Path('/app/locales') / norm / 'common.json',
    ):
        if candidate.is_file():
            data = json.loads(candidate.read_text(encoding='utf-8'))
            _CACHE[norm] = data
            return data
    return {}


def normalize_locale(header_or_locale: str | None) -> str:
    if not header_or_locale:
        env_default = os.getenv('RIGHAVEN_DEFAULT_LOCALE', DEFAULT_LOCALE).strip().lower()
        return env_default if env_default in SUPPORTED_LOCALES else DEFAULT_LOCALE
    raw = str(header_or_locale).strip().lower()
    for token in raw.replace(';', ',').split(','):
        code = token.strip().split('-')[0].split('_')[0]
        if code in SUPPORTED_LOCALES:
            return code
    return DEFAULT_LOCALE


def resolve_request_locale(request) -> str:
    if request is None:
        return normalize_locale(None)
    query_lang = request.query_params.get('lang') or request.query_params.get('locale')
    if query_lang:
        return normalize_locale(query_lang)
    accept_lang = request.headers.get('accept-language')
    return normalize_locale(accept_lang)


def translate(key: str, locale: str | None = None, **kwargs) -> str:
    norm = normalize_locale(locale)
    dictionary = load_dictionary(norm)
    node = dictionary
    for part in key.split('.'):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            node = None
            break
    if not isinstance(node, str) and norm != DEFAULT_LOCALE:
        node = load_dictionary(DEFAULT_LOCALE)
        for part in key.split('.'):
            node = node.get(part) if isinstance(node, dict) else None
    text = node if isinstance(node, str) else key
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text


def localize_clarification(questions: list[str], locale: str | None = None) -> dict:
    norm = normalize_locale(locale)
    prompt = translate('harness.ask_clarification_prompt', locale=norm)
    notice = translate('notifications.clarification_needed', locale=norm)
    return {
        'locale': norm,
        'prompt': prompt,
        'notice': notice,
        'questions': list(questions or []),
    }
