"""Per-model token prices set by an administrator, used to estimate assignment costs.

Prices are per million tokens in one currency for the installation. Costs are
estimates computed when the report is read: changing a price updates past
estimates too, and a model without a price has no estimated cost.
"""
import json
import re

from . import state

CURRENCIES = ('USD', 'EUR', 'GBP', 'CHF')
MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}')
FIELDS = ('input', 'cached_input', 'output')


def path():
    return state.STATE / 'model-prices.json'


def load():
    try:
        value = json.loads(path().read_text())
    except (OSError, ValueError):
        return {'currency': 'USD', 'models': {}}
    return value if isinstance(value, dict) and isinstance(value.get('models'), dict) else {'currency': 'USD', 'models': {}}


def validate(value):
    if not isinstance(value, dict) or value.get('currency') not in CURRENCIES or not isinstance(value.get('models'), dict):
        raise ValueError('Prezzi: indica currency (' + ', '.join(CURRENCIES) + ') e models')
    if len(value['models']) > 200:
        raise ValueError('Prezzi: al massimo 200 modelli')
    models = {}
    for model, price in value['models'].items():
        if not isinstance(model, str) or not MODEL.fullmatch(model) or not isinstance(price, dict) or set(price) - set(FIELDS):
            raise ValueError('Prezzi: modello o campi non validi (input, cached_input, output per milione di token)')
        clean = {}
        for field in FIELDS:
            number = price.get(field, price.get('input') if field == 'cached_input' else 0)
            if type(number) not in (int, float) or not 0 <= number <= 100000:
                raise ValueError('Prezzi: valori tra 0 e 100000 per milione di token')
            clean[field] = float(number)
        models[model] = clean
    return {'currency': value['currency'], 'models': models}


def save(value):
    from .state import atomic_json
    clean = validate(value)
    atomic_json(path(), clean)
    return clean


def cost(prices, model, input_tokens, cached_tokens, output_tokens):
    """Estimated cost, or None when the model has no price."""
    price = prices['models'].get(model or '')
    if price is None:
        return None
    cached = min(cached_tokens or 0, input_tokens or 0)
    return round(((input_tokens or 0) - cached) * price['input'] / 1e6 + cached * price['cached_input'] / 1e6
                 + (output_tokens or 0) * price['output'] / 1e6, 6)
