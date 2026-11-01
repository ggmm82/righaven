"""Recipes: phased, multi-tool workflows offered on demand.

Skills say how to work (method and expertise), environments say with which
tools, and a recipe is the phased path that combines them for a kind of result.
A recipe tells the user what to attach, what will be asked and what they get,
and tells the coordinator which skills and tools to use. Its tools are prepared
on demand at the first assignment; nothing has to be activated beforehand.

Built-in recipes ship in recipes.json. Users create their own (or duplicate a
built-in one) from the Recipes page and may publish them to the catalog, where
everyone finds them next to environments and skills; administrators can withdraw them.
"""
import json
import re
import secrets
from functools import lru_cache
from pathlib import Path

from . import state

LOCALES = ('it', 'en')
INTAKE = ('source', 'destination', 'bi', 'frequency', 'notes')
TEXT_LISTS = ('attach_required', 'attach_optional', 'attach_never', 'questions', 'outputs', 'prerequisites')
RECIPE_ID = re.compile(r'[a-z][a-z0-9-]{1,39}\Z')


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Ricetta: testo mancante o oltre ' + str(limit) + ' caratteri')
    return value.strip()


def validate(recipe, known_tools=None):
    if not isinstance(recipe, dict) or not RECIPE_ID.fullmatch(str(recipe.get('id', ''))):
        raise ValueError('Ricetta: id minuscolo con lettere, cifre e trattini')
    if not str(recipe.get('skill', '')).startswith('skill-'):
        raise ValueError('Ricetta ' + recipe['id'] + ': skill gestita richiesta')
    tools = recipe.get('tools')
    if not isinstance(tools, list) or not tools or (known_tools is not None and set(tools) - set(known_tools)):
        raise ValueError('Ricetta ' + recipe['id'] + ': strumenti fuori catalogo')
    for locale in LOCALES:
        text = recipe.get(locale)
        if not isinstance(text, dict):
            raise ValueError('Ricetta ' + recipe['id'] + ': testi ' + locale + ' mancanti')
        for field, limit in (('title', 80), ('summary', 400), ('when', 400)):
            _text(text.get(field), limit)
        for field in TEXT_LISTS:
            items = text.get(field, [])
            if not isinstance(items, list) or len(items) > 12 or any(_text(i, 400) is None for i in items):
                raise ValueError('Ricetta ' + recipe['id'] + ': elenco ' + field + ' non valido')
        if not text.get('attach_required') or not text.get('outputs'):
            raise ValueError('Ricetta ' + recipe['id'] + ': indica cosa allegare e cosa si ottiene')
        phases = text.get('phases')
        if not isinstance(phases, list) or not 1 <= len(phases) <= 12 or any(
                not isinstance(p, dict) or type(p.get('checkpoint')) is not bool for p in phases):
            raise ValueError('Ricetta ' + recipe['id'] + ': fasi non valide')
        for phase in phases:
            _text(phase.get('title'), 80)
            _text(phase.get('detail'), 300)
    if len(recipe['it']['phases']) != len(recipe['en']['phases']):
        raise ValueError('Ricetta ' + recipe['id'] + ': le fasi devono coincidere nelle due lingue')
    return recipe


@lru_cache(maxsize=1)
def _load():
    value = json.loads((state.ROOT / 'recipes.json').read_text())
    known = {a['id'] for a in state.applications()}
    recipes = [validate(r, known) for r in value['recipes']]
    if len({r['id'] for r in recipes}) != len(recipes):
        raise ValueError('Ricette con id duplicato')
    return tuple(recipes)


def recipes():
    return list(_load())


def skills():
    return frozenset(r['skill'] for r in _load())


def locale_key(locale):
    return 'it' if str(locale or '').lower().startswith('it') else 'en'


def skills_of(recipe):
    return list(recipe.get('skills') or [recipe['skill']])


def card(recipe, locale, user_id=None):
    text = recipe[locale_key(locale)]
    custom = bool(recipe.get('owner'))
    return {'id': recipe['id'], 'skill': recipe['skill'], 'skills': skills_of(recipe), 'environment': recipe.get('environment'),
            'tools': list(recipe['tools']), 'custom': custom, 'shared': bool(recipe.get('shared')) if custom else True,
            'mine': custom and recipe['owner'] == user_id, 'revision': recipe.get('revision', 0), 'based_on': recipe.get('based_on'),
            'intake': list(recipe.get('intake', INTAKE)),
            **{k: text[k] for k in ('title', 'summary', 'when', 'phases')}, 'starter': text.get('starter', ''),
            **{k: list(text.get(k, [])) for k in TEXT_LISTS}}


def visible(user_id=None):
    """Built-in recipes, the user's own and those an administrator shared."""
    return [*_load(), *[r for r in _custom() if r['shared'] or (user_id and r['owner'] == user_id)]]


def find(identifier, user_id=None):
    recipe = next((r for r in visible(user_id) if r['id'] == identifier), None)
    if recipe is None:
        raise ValueError('Ricetta non trovata')
    return recipe


def catalog(locale='it', user_id=None):
    return [card(r, locale, user_id) for r in visible(user_id)]


def detail(identifier, locale='it', user_id=None):
    return card(find(identifier, user_id), locale, user_id)


def coordinator_index(skill_names=None, user_id=None):
    """Compact list for harness_skills: when to propose a recipe and which skill to read."""
    rows = []
    for recipe in visible(user_id):
        if skill_names is not None and not set(skills_of(recipe)) <= set(skill_names):
            continue
        text = recipe['it']
        rows.append({'id': recipe['id'], 'title': text['title'], 'when': text['when'], 'skill': recipe['skill'],
                     **({'skills': skills_of(recipe), 'environment': recipe.get('environment'), 'custom': True} if recipe.get('owner') else {}),
                     'keywords': recipe.get('keywords', [])[:20], 'tools': recipe['tools'],
                     'attach_required': text['attach_required'], 'questions': text['questions'],
                     'checkpoints': [p['title'] for p in text['phases'] if p['checkpoint']]})
    return rows


# ---- User recipes -----------------------------------------------------------------------------
DRAFT_TEXT = {'title': 80, 'summary': 400, 'when': 400}


def _store():
    folder = state.STATE / 'recipes'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _custom():
    folder = state.STATE / 'recipes'
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.glob('*.json')):
        if path.is_symlink() or path.stat().st_size > 200000:
            continue
        try:
            rows.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    return rows


def _slug(title):
    base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:28].strip('-')
    if not base or not base[0].isalpha():
        base = 'ricetta' + ('-' + base if base else '')
    return base + '-' + secrets.token_hex(3)


def _lines(value, field):
    if not isinstance(value, list) or len(value) > 12 or not all(isinstance(i, str) for i in value):
        _bad(field)
    return [_text(item, 400) for item in value if item.strip()]


def _bad(field):
    raise ValueError('Ricetta: elenco ' + field + ' non valido')


def compose(draft, owner, skill_names, previous=None, known_tools=None):
    """Turn the editor draft into a recipe with the same shape as built-in ones, plus its guided workflow."""
    from .environments import PRESETS
    from .project_skills import redact_memory
    if not isinstance(draft, dict):
        raise ValueError('Ricetta non valida')
    if redact_memory(draft) != draft:
        raise ValueError('Use Connections for credentials, never recipe texts')
    text = {k: _text(draft.get(k), limit) for k, limit in DRAFT_TEXT.items()}
    for field in TEXT_LISTS:
        text[field] = _lines(draft.get(field, []), field)
    phases = draft.get('phases')
    if not isinstance(phases, list) or not 1 <= len(phases) <= 12:
        raise ValueError('Ricetta: da una a dodici fasi')
    text['phases'] = [{'title': _text(p.get('title'), 80), 'detail': _text(p.get('detail'), 300), 'checkpoint': p.get('checkpoint') is not False}
                      if isinstance(p, dict) else _bad('phases') for p in phases]
    text['starter'] = ''
    chosen = draft.get('skills')
    if not isinstance(chosen, list) or not 1 <= len(chosen) <= 8 or not all(isinstance(s, str) for s in chosen):
        raise ValueError('Choose one to eight skills for this recipe')
    chosen = list(dict.fromkeys(chosen))
    if set(chosen) - set(skill_names):
        raise ValueError('Enable the selected skills in your account first: ' + ', '.join(sorted(set(chosen) - set(skill_names))))
    environment = draft.get('environment') or None
    presets = {p['id']: p for p in PRESETS}
    if environment is not None and environment not in presets:
        raise ValueError('Unknown environment')
    tools = draft.get('tools') or []
    if not isinstance(tools, list) or len(tools) > 30 or not all(isinstance(x, str) for x in tools):
        raise ValueError('Choose an environment or at least one tool')
    tools = list(dict.fromkeys(tools or (presets[environment]['tools'] if environment else [])))
    keywords = draft.get('keywords') or []
    if not isinstance(keywords, list) or len(keywords) > 20 or not all(isinstance(k, str) and 0 < len(k.strip()) <= 40 for k in keywords):
        raise ValueError('Ricetta: parole chiave non valide')
    guidance = draft.get('guidance') or ''
    if not isinstance(guidance, str) or len(guidance) > 2000:
        raise ValueError('Ricetta: indicazioni per la squadra oltre 2000 caratteri')
    revision = (previous or {}).get('revision', 0) + 1
    identifier = previous['id'] if previous else _slug(text['title'])
    recipe = {'id': identifier, 'owner': previous['owner'] if previous else owner, 'shared': bool((previous or {}).get('shared')),
              'revision': revision, 'created_at': (previous or {}).get('created_at') or utc(), 'updated_at': utc(),
              'based_on': draft.get('based_on') if isinstance(draft.get('based_on'), str) else (previous or {}).get('based_on'),
              'skill': chosen[0], 'skills': chosen, 'environment': environment, 'tools': tools, 'intake': ['notes'],
              'keywords': [k.strip() for k in keywords], 'it': text, 'en': text,
              'workflow': {'version': revision, 'guidance': guidance.strip(), 'policy': None,
                           'stages': [{'id': 'phase-' + str(i + 1), 'title': {'it': p['title'], 'en': p['title']},
                                       'outcome': {'it': p['detail'], 'en': p['detail']},
                                       'depends_on': ['phase-' + str(i)] if i else [], 'gate': p['checkpoint']}
                                      for i, p in enumerate(text['phases'])]}}
    if not tools:
        raise ValueError('Choose an environment or at least one tool')
    return validate(recipe, known_tools if known_tools is not None else {a['id'] for a in state.applications()})


def utc():
    from .progress import utcnow
    return utcnow()


def _path(identifier):
    if not RECIPE_ID.fullmatch(str(identifier)):
        raise ValueError('Ricetta non trovata')
    return _store() / (identifier + '.json')


def _owned(identifier, owner, administrator=False):
    path = _path(identifier)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Ricetta non trovata')
    recipe = json.loads(path.read_text())
    if recipe['owner'] != owner and not (administrator and recipe.get('shared')):
        raise ValueError('Only the author can change this recipe')
    return recipe


def create(owner, draft, skill_names):
    recipe = compose(draft, owner, skill_names)
    if any(r['id'] == recipe['id'] for r in _load()):
        raise ValueError('Ricette con id duplicato')
    state.atomic_json(_path(recipe['id']), recipe)
    return recipe


def update(owner, identifier, draft, skill_names, expected_revision, administrator=False):
    previous = _owned(identifier, owner, administrator)
    if previous['revision'] != expected_revision:
        raise ValueError('Recipe changed; reload before saving')
    recipe = compose(draft, owner, skill_names, previous)
    state.atomic_json(_path(identifier), recipe)
    return recipe


def share(owner, identifier, shared, administrator):
    """Publish a recipe to the catalog (Community Gallery and Recipes) or withdraw it: its author, or an administrator."""
    path = _path(identifier)
    if not path.is_file():
        raise ValueError('Ricetta non trovata')
    recipe = json.loads(path.read_text())
    if recipe['owner'] != owner and not administrator:
        raise ValueError('Only the author or an administrator publishes this recipe')
    recipe.update(shared=bool(shared), revision=recipe['revision'] + 1, updated_at=utc())
    state.atomic_json(path, recipe)
    return recipe


def delete(owner, identifier, administrator=False):
    _owned(identifier, owner, administrator)
    _path(identifier).unlink()


def draft(identifier, locale='it', user_id=None):
    """Editable copy of a visible recipe: the starting point to duplicate a built-in one."""
    recipe = find(identifier, user_id)
    text = recipe[locale_key(locale)]
    return {'based_on': recipe['id'], **{k: text[k] for k in DRAFT_TEXT}, **{k: list(text.get(k, [])) for k in TEXT_LISTS},
            'phases': [dict(p) for p in text['phases']], 'skills': skills_of(recipe), 'environment': recipe.get('environment'),
            'tools': list(recipe['tools']), 'keywords': list(recipe.get('keywords', []))[:20],
            'guidance': recipe.get('workflow', {}).get('guidance', '')}
