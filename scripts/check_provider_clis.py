#!/usr/bin/env python3
"""Check actual pinned CLI entry points; no credentials or provider requests."""
import subprocess
import json
from pathlib import Path


def main():
    antigravity_version = json.loads(Path(__file__).with_name('antigravity.lock.json').read_text())['version']
    lock = Path(__file__).resolve().parents[1] / 'versions.lock.json'
    if not lock.is_file(): lock = Path(__file__).with_name('versions.lock.json')
    codex_version = json.loads(lock.read_text())['cli_runtimes']['codex']
    contracts = [
        (['codex', '--version'], [codex_version]),
        (['codex', 'login', '--help'], ['--device-auth']),
        (['codex', 'app-server', '--help'], ['--listen', 'stdio://', 'generate-json-schema']),
        (['codex', 'features', 'list'], ['image_generation']),
        (['agy', '--version'], [antigravity_version]),
        (['agy', '--help'], ['--print', '--output-format', '--model', '--add-dir',
                            '--json-schema', '--agent', '--disable-slash-commands',
                            '--print-timeout', '--dangerously-skip-permissions']),
        (['agy', 'models', '--help'], ['List available models']),
    ]
    for command, expected in contracts:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
        text = result.stdout + result.stderr
        for token in expected:
            if token not in text:
                raise RuntimeError(f'{command}: contratto CLI mancante: {token}')
        print('OK:', ' '.join(command))


if __name__ == '__main__':
    main()
