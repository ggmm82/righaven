"""Errors are written once and served in the viewer's language.

The source text is the key (as in gettext). locales/en/errors.json maps every
source message, or the fixed beginning of a composed message, to English, with
null for text already in English; locales/it/errors.json maps those English
sources to Italian. A test extracts every raised message so a new one cannot
ship without a decision in both catalogs.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAISED = {'ValueError', 'HTTPException', 'RuntimeError', 'PermissionError', 'FileNotFoundError', 'TimeoutError'}
_CATALOGS = {}


def catalog(locale):
    if locale not in _CATALOGS:
        for candidate in (ROOT / 'locales' / locale / 'errors.json', Path('/app/locales') / locale / 'errors.json'):
            if candidate.is_file():
                _CATALOGS[locale] = json.loads(candidate.read_text())
                break
        else:
            _CATALOGS[locale] = {}
    return _CATALOGS[locale]


def localize(message, locale):
    """The message in the viewer's language; unknown text is returned unchanged.

    Sources are mostly Italian (translated by locales/en) and partly English
    (translated by locales/it). null means the text is the same in both.
    """
    if not isinstance(message, str):
        return message
    language = 'en' if str(locale or '').lower().startswith('en') else 'it'
    entries = catalog(language)
    if message in entries:
        return entries[message] or message
    prefix = max((key for key in entries if key.endswith((': ', ' ', '«', '(', "'")) and message.startswith(key)), key=len, default=None)
    if prefix is None:
        return message
    return (entries[prefix] or prefix) + message[len(prefix):]


async def localized_http_exception(request, exc):
    """FastAPI handler: error messages in the viewer's language; structured details pass through."""
    from fastapi.exception_handlers import http_exception_handler
    from starlette.exceptions import HTTPException
    from .i18n import resolve_request_locale
    if isinstance(exc.detail, str):
        exc = HTTPException(exc.status_code, localize(exc.detail, resolve_request_locale(request)), exc.headers)
    return await http_exception_handler(request, exc)


def _literal_start(node):
    """The fixed text a composed message starts with."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        text, complete = _literal_start(node.left)
        return text, False if text is not None else complete
    if isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant):
        return node.values[0].value, False
    return None, False


def raised_messages(paths=None):
    """(message, composed) for every exception raised with a fixed message in the Gateway package."""
    found = set()
    for path in paths or sorted((ROOT / 'righaven').glob('*.py')):
        for node in ast.walk(ast.parse(Path(path).read_text())):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and getattr(node.exc.func, 'id', '') in RAISED):
                continue
            args = node.exc.args
            argument = (args[1] if len(args) > 1 else None) if node.exc.func.id == 'HTTPException' else (args[0] if args else None)
            for keyword in node.exc.keywords:
                if keyword.arg == 'detail':
                    argument = keyword.value
            text, complete = _literal_start(argument) if argument is not None else (None, False)
            if text and text.strip():
                found.add((text, not complete))
    return sorted(found)
