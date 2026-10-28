#!/usr/bin/env python3
"""Release notes for the Compose produced after the full acceptance pipeline."""
import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.commit):
        parser.error('Serve lo SHA completo del commit verificato')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f'''RigHaven · runtime verificati del commit `{args.commit}`.

- Configurazione unica Codex, Antigravity CLI e DeepSeek per coordinatore e specialisti.
- Login Google tramite il binario ufficiale agy, rinnovo Codex tramite app-server, credenziali private.
- Ricette operative e collaudi di file reali per tutti i 13 strumenti.
- Immagini, schema RigHaven, CLI/MCP e avvio autenticato verificati dalla CI.

Il Compose allegato usa soltanto le immagini di questo commit. Non contiene credenziali.
URL stabile per Hostinger: https://github.com/righaven/righaven/releases/latest/download/compose.hostinger.yaml

Conservare nome del progetto, variabili e volumi durante l'aggiornamento. Il rilascio
non esegue il deploy sul VPS. Le prove delle CLI sono rappresentative e non certificano
ogni funzione o la qualità percettiva. OAuth con account reali e capacità del VPS
vanno verificati sul proprio ambiente.
''')


if __name__ == '__main__':
    main()
