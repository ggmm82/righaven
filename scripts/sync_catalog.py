#!/usr/bin/env python3
"""Propagate the application catalog without adding provider/model settings."""
import argparse
import json
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def sync(root=ROOT):
    root = Path(root)
    lock_path = root / 'versions.lock.json'
    lock = json.loads(lock_path.read_text())
    apps = lock['applications']
    ids = [app['id'] for app in apps]
    if not all(re.fullmatch(r'[a-z][a-z0-9-]*', identifier) for identifier in ids):
        raise ValueError('Identificatore applicazione non valido')
    if len(set(ids)) != len(ids):
        raise ValueError('Identificatori duplicati')
    for identifier in ids:
        skill = root / 'skills/custom' / ('skill-' + identifier) / 'SKILL.md'
        if not skill.is_file():
            raise ValueError(f'Scrivere e collaudare prima la skill: {identifier}')
    path = root / 'config/righaven.yaml'
    content = yaml.safe_load(path.read_text())
    content['subagents']['custom_agents'] = {
        app['id']: {
            'description': f"{app['role']}: {app['description']} Usa {app['executable']}.",
            'system_prompt': f"Sei lo specialista {app['id']}. Per eseguire il lavoro invoca "
                f"harness_delegate con agent=\"{app['id']}\", includendo input, percorsi, sorgenti modificabili, app di apertura e criteri "
                'di accettazione. Eredita il modello unico della squadra. Non eseguire CLI nel '
                'Gateway. Riporta risultati e limiti della delega.',
            'skills': ['skill-workspace', 'skill-' + app['id']],
            'model': 'inherit', 'max_turns': 50, 'timeout_seconds': 1800,
            'disallowed_tools': ['task', 'ask_clarification', 'present_files'],
        } for app in apps}
    content['subagents']['max_total_per_run'] = max(content['subagents']['max_total_per_run'], len(apps) + 3)
    # Append dynamic routing rather than relying exclusively on the historical list.
    overlay = content['lead_prompt_overlay']['append'].split('\nCatalogo operativo aggiornato:')[0]
    content['lead_prompt_overlay']['append'] = overlay + '\nCatalogo operativo aggiornato: ' + '; '.join(
        f"{app['id']} per {app['role']} ({app['description']})" for app in apps) + '.'
    serialized = yaml.safe_dump(content, sort_keys=False, allow_unicode=True)
    path.write_text(serialized)
    (root / 'righaven/righaven.yaml').write_text(serialized)
    (root / 'righaven/versions.lock.json').write_bytes(lock_path.read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    sync()
