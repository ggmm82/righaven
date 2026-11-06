"""Worker capability policy: fixed read-only job manifest, no environment override."""
import json
from pathlib import Path


def allowed_ids(installed):
    path = Path('/job.json')
    if not path.exists():
        return set(installed)  # Unscoped build/acceptance, before user jobs exist.
    policy = json.loads(path.read_text()).get('capability_policy')
    if not isinstance(policy, dict) or not isinstance(policy.get('allowed'), list):
        raise ValueError('Politica delle capacità assente: avvia una sandbox aggiornata')
    return set(policy['allowed']) & set(installed)
