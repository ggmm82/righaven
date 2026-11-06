#!/usr/bin/env python3
"""Controlli reali sulle CLI installate. --render aggiunge export di prova."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET


def run(command, timeout=120):
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return {'command': command, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'command': command, 'returncode': -1, 'stdout': '', 'stderr': str(error)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--mcp', action='store_true')
    parser.add_argument('--workspace-root', type=Path, default=Path('/mnt/user-data'))
    parser.add_argument('--output', type=Path, default=Path('/tmp/skill-checks.json'))
    args = parser.parse_args()
    root = Path(os.environ.get('RIGHAVEN_INSTALL_ROOT', '/opt/righaven'))
    lock = json.loads((root / 'versions.lock.json').read_text())
    checks = []
    for app in lock['applications']:
        reference = root / 'reference' / app['id']
        reference.mkdir(parents=True, exist_ok=True)
        if app['id'] == 'calibre':
            # Fail the build with the missing library's name instead of Qt's
            # generic xcb-cursor warning during a later publication job.
            bundle = root / 'apps/calibre'
            linked = run(['env', 'LD_LIBRARY_PATH=' + str(bundle / 'lib'), 'ldd',
                          str(bundle / 'plugins/platforms/libqxcb.so')])
            missing = [line.strip() for line in (linked['stdout'] + linked['stderr']).splitlines() if 'not found' in line]
            linked['ok'] = linked['returncode'] == 0 and not missing
            if missing: linked['stderr'] = '\n'.join(missing)
            checks.append(linked)
        version = run([app['executable'], '--version'])
        version['ok'] = version['returncode'] == 0 and app['version'].removeprefix('v') in version['stdout']
        checks.append(version)
        help_result = run([app['executable'], '--help'])
        help_text = help_result['stdout'] + help_result['stderr']
        # DeckCraft v0.7.0 prints usage and exits 1 on --help; it is not a linkage error.
        help_result['ok'] = help_result['returncode'] in (0, 1, 2) and ('usage' in help_text.lower() or app['executable'] in help_text)
        checks.append(help_result)
        (reference / 'help.txt').write_text(help_text, encoding='utf-8')
        registry = run([app['executable'], *app['registry_args']])
        registry['ok'] = registry['returncode'] == 0 and bool(registry['stdout'].strip())
        (reference / 'commands.txt').write_text(registry['stdout'], encoding='utf-8')
        checks.append(registry)
        if args.mcp:
            args.workspace_root.mkdir(parents=True, exist_ok=True)
            mcp = run(['craft', 'tools', app['id'], '--out', str(reference / 'mcp-tools.json')], timeout=210)
            mcp['ok'] = mcp['returncode'] == 0
            checks.append(mcp)
    if args.render:
        with tempfile.TemporaryDirectory(prefix='skill-render-') as directory:
            d = Path(directory)
            (d / 'input.md').write_text('# Prova RigHaven\n\n| Voce | Importo |\n| --- | ---: |\n| A | 10,00 |\n| B | 20,00 |\n| C | 30,00 |\n| Totale | 60,00 |\n', encoding='utf-8')
            tasks = [
                (['gridcraft-cli', 'eval', '=SUM(1,2,3)'], None),
                (['wordcraft-cli', 'convert', str(d/'input.md'), str(d/'documento.docx')], d/'documento.docx'),
                (['wordcraft-cli', 'convert', str(d/'documento.docx'), str(d/'documento.pdf')], d/'documento.pdf'),
                (['pdfcraft-cli', 'info', str(d/'documento.pdf')], None),
                (['pdfcraft-cli', 'text', str(d/'documento.pdf')], None),
                (['deckcraft-cli', 'render', '--sample', '--slide', '1', str(d/'slide.png')], d/'slide.png'),
                (['cadcraft-cli', 'run', '--sample', '--save', str(d/'disegno.dxf')], d/'disegno.dxf'),
            ]
            for command, expected in tasks:
                result = run(command, timeout=180)
                result['ok'] = result['returncode'] == 0 and (expected is None or (expected.is_file() and expected.stat().st_size > 0))
                if command[:2] == ['gridcraft-cli', 'eval']:
                    result['ok'] = result['ok'] and result['stdout'].strip() == '6'
                if command[:2] == ['wordcraft-cli', 'convert'] and expected and expected.suffix == '.docx' and result['ok']:
                    with zipfile.ZipFile(expected) as archive:
                        tree = ET.fromstring(archive.read('word/document.xml'))
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    content = ''.join(n.text or '' for n in tree.findall('.//w:t', ns))
                    result['ok'] = len(tree.findall('.//w:tbl', ns)) == 1 and '60,00' in content
                if command[:2] == ['pdfcraft-cli', 'text']:
                    result['ok'] = result['ok'] and '60,00' in result['stdout']
                checks.append(result)
    report = {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'passed': all(x['ok'] for x in checks), 'checks': checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for c in checks:
        print(('OK' if c['ok'] else 'FAIL'), ' '.join(c['command']))
        if not c['ok']:
            print(c['stderr'][-2000:])
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
