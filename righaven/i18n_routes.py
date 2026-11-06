"""REST endpoints for querying i18n dictionaries and resolving Accept-Language."""
from fastapi import APIRouter, HTTPException, Request
from .i18n import SUPPORTED_LOCALES, load_dictionary, normalize_locale, resolve_request_locale, translate

router = APIRouter(prefix='/api/v1/i18n', tags=['RigHaven i18n'])


@router.get('')
def get_active_locale(request: Request):
    locale = resolve_request_locale(request)
    return {
        'locale': locale,
        'default_locale': 'en',
        'supported_locales': list(SUPPORTED_LOCALES),
        'dictionary': load_dictionary(locale),
    }


@router.get('/{locale}')
def get_dictionary(locale: str):
    if locale.lower() not in SUPPORTED_LOCALES:
        raise HTTPException(404, f"Unsupported locale '{locale}'. Supported: en, it.")
    norm = normalize_locale(locale)
    return {
        'locale': norm,
        'dictionary': load_dictionary(norm),
    }
