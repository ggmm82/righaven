"""Recipes: tested, multi-tool workflows offered on demand.

A recipe tells the user what to attach, what will be asked and what they get,
and tells the coordinator which skill and tools to use. Its tools are prepared
on demand at the first assignment; nothing has to be activated beforehand.
"""
import json
import re
from functools import lru_cache

from . import state

LOCALES = ('it', 'en')
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
        for field, limit in (('title', 80), ('summary', 400), ('when', 400), ('starter', 1500)):
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


def card(recipe, locale):
    text = recipe[locale_key(locale)]
    return {'id': recipe['id'], 'skill': recipe['skill'], 'environment': recipe.get('environment'), 'tools': list(recipe['tools']),
            **{k: text[k] for k in ('title', 'summary', 'when', 'phases', 'starter')},
            **{k: list(text.get(k, [])) for k in TEXT_LISTS}}


def catalog(locale='it'):
    return [card(r, locale) for r in _load()]


def detail(identifier, locale='it'):
    recipe = next((r for r in _load() if r['id'] == identifier), None)
    if recipe is None:
        raise ValueError('Ricetta non trovata')
    return card(recipe, locale)


def coordinator_index(skill_names=None):
    """Compact list for harness_skills: when to propose a recipe and which skill to read."""
    rows = []
    for recipe in _load():
        if skill_names is not None and recipe['skill'] not in skill_names:
            continue
        text = recipe['it']
        rows.append({'id': recipe['id'], 'title': text['title'], 'when': text['when'], 'skill': recipe['skill'],
                     'keywords': recipe.get('keywords', [])[:20], 'tools': recipe['tools'],
                     'attach_required': text['attach_required'], 'questions': text['questions'],
                     'checkpoints': [p['title'] for p in text['phases'] if p['checkpoint']]})
    return rows
