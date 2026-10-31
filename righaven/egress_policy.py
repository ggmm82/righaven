"""Which Internet domains an assignment worker may reach.

RIGHAVEN_WORKER_EGRESS=open keeps the previous behaviour (bridge network).
With allowlist, workers run on an internal network whose only exit is the
egress proxy: the model provider of the job is always granted, and a role may
add at most eight domains, each with the reason the coordinator declared.
"""
import os
import re
from urllib.parse import urlsplit

MODES = ('open', 'allowlist')
DOMAIN = re.compile(r'\.?[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+')
# Endpoints contacted by each model CLI or API client from inside the worker.
PROVIDERS = {
    'codex': ['api.openai.com', 'chatgpt.com', 'auth.openai.com', 'ab.chatgpt.com'],
    'claude': ['api.anthropic.com', 'console.anthropic.com', 'statsig.anthropic.com', 'claude.ai', 'platform.claude.com'],
    'gemini': ['.googleapis.com', 'accounts.google.com', 'oauth2.googleapis.com', 'play.googleapis.com'],
    'deepseek': ['api.deepseek.com'],
    'openai': [],
}


def mode():
    value = os.getenv('RIGHAVEN_WORKER_EGRESS', 'open').strip().lower() or 'open'
    if value not in MODES:
        raise ValueError('RIGHAVEN_WORKER_EGRESS must be open or allowlist')
    return value


def validate_network(value):
    """Role field: [] (model provider only) or up to eight {domain, reason} grants."""
    if value in (None, '', []):
        return []
    if not isinstance(value, list) or len(value) > 8:
        raise ValueError('network: al massimo otto domini, ciascuno con il motivo')
    result, seen = [], set()
    for item in value:
        domain = item.get('domain', '') if isinstance(item, dict) else ''
        reason = item.get('reason', '') if isinstance(item, dict) else ''
        domain = domain.strip().lower() if isinstance(domain, str) else ''
        if not DOMAIN.fullmatch(domain) or domain.rsplit('.', 1)[-1].isdigit() or domain.count('.') < (2 if domain.startswith('.') else 1):
            raise ValueError('network: dominio non valido; usa nomi come fonts.googleapis.com o .example.org')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 300:
            raise ValueError('network: ogni dominio richiede un motivo breve')
        if domain not in seen:
            seen.add(domain)
            result.append({'domain': domain, 'reason': reason.strip()})
    return result


def allowed_domains(engine, network=(), base_url=''):
    """Model provider domains plus the role's grants, without duplicates."""
    domains = list(PROVIDERS.get(engine, []))
    host = urlsplit(base_url or '').hostname
    if host:
        domains.append(host.lower())
    domains += [grant['domain'] for grant in network or []]
    return list(dict.fromkeys(domains))
