#!/usr/bin/env python3
"""Create local .env without downloading repositories or overwriting secrets."""
from pathlib import Path
import secrets
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if path.exists():
    print('.env esistente conservato. Controlla RIGHAVEN_PASSWORD prima del deploy.')
else:
    template=(root/'.env.example').read_text()
    path.write_text(template.replace('RIGHAVEN_PASSWORD=\n','RIGHAVEN_PASSWORD='+secrets.token_urlsafe(32)+'\n'))
    path.chmod(0o600)
    print('.env creato con password casuale. Aprilo per le impostazioni; poi docker compose build e docker compose up -d.')
