#!/usr/bin/env python3
"""Accesso CLI/MCP locale alle applicazioni del catalogo nella sandbox RigHaven."""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(os.environ.get('RIGHAVEN_INSTALL_ROOT', '/opt/righaven'))


class McpSession:
    def __init__(self, argv, timeout=180):
        self.timeout = timeout
        self.sequence = 0
        self.messages = queue.Queue()
        self.errors = tempfile.TemporaryFile(mode='w+t', encoding='utf-8')
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.errors, text=True, encoding='utf-8', bufsize=1)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                if not line.strip():
                    continue
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    self.messages.put(RuntimeError('Il server MCP ha scritto stdout non JSON: ' + line[:300]))
        finally:
            self.messages.put(EOFError('Il processo MCP si è chiuso'))

    def send(self, message):
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
        self.process.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'Timeout MCP: {method}')
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f'Timeout MCP: {method}') from exc
            if isinstance(message, Exception):
                raise message
            if 'method' in message and 'id' in message:
                if message['method'] == 'roots/list':
                    self.send({'jsonrpc': '2.0', 'id': message['id'], 'result': {'roots': [{'uri': 'file:///mnt/user-data', 'name': 'RigHaven workspace'}]}})
                else:
                    self.send({'jsonrpc': '2.0', 'id': message['id'], 'error': {'code': -32601, 'message': 'Client method not supported'}})
                continue
            if message.get('id') != request_id:
                continue
            if 'error' in message:
                raise RuntimeError(json.dumps(message['error'], ensure_ascii=False))
            result = message.get('result', {})
            if isinstance(result, dict) and result.get('isError'):
                raise RuntimeError(json.dumps(result, ensure_ascii=False))
            return result

    def initialize(self):
        self.call('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {'roots': {'listChanged': False}},
                                 'clientInfo': {'name': 'righaven', 'version': '1.0'}})
        self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=5)
        self.process.stdin.close()
        self.process.stdout.close()
        self.errors.close()


def resolve_references(value, results):
    if isinstance(value, dict) and set(value) == {'$result'}:
        parts = str(value['$result']).split('.')
        if not parts[0].isdecimal() or int(parts[0]) >= len(results):
            raise ValueError('Riferimento $result: indice precedente non valido')
        result = results[int(parts[0])]
        for part in parts[1:]:
            if part == '$json':
                if not isinstance(result, str):
                    raise ValueError('Riferimento $result: $json richiede testo JSON')
                try:
                    result = json.loads(result)
                except ValueError:
                    raise ValueError('Riferimento $result: testo JSON non valido') from None
            elif isinstance(result, list):
                if not part.isdecimal() or int(part) >= len(result):
                    raise ValueError('Riferimento $result: indice di lista non valido')
                result = result[int(part)]
            elif isinstance(result, dict) and part in result:
                result = result[part]
            else:
                raise ValueError('Riferimento $result: percorso non valido')
        return result
    if isinstance(value, dict):
        return {k: resolve_references(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_references(v, results) for v in value]
    return value


def save_json(value, output):
    text = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if output:
        Path(output).write_text(text, encoding='utf-8')
        print(output)
    else:
        print(text, end='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    subs.add_parser('list')
    p = subs.add_parser('capabilities'); p.add_argument('app', nargs='?'); p.add_argument('--all-commands', action='store_true')
    for name in ('help', 'commands'):
        p = subs.add_parser(name)
        p.add_argument('app')
    p = subs.add_parser('tools'); p.add_argument('app'); p.add_argument('--out')
    p = subs.add_parser('batch'); p.add_argument('app'); p.add_argument('file'); p.add_argument('--out'); p.add_argument('--timeout', type=int, default=None)
    p = subs.add_parser('run'); p.add_argument('app'); p.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    apps = {a['id']: a for a in json.loads((ROOT / 'versions.lock.json').read_text())['applications']}
    try:
        from runtime_policy import allowed_ids
    except ImportError:
        from scripts.runtime_policy import allowed_ids
    allowed = allowed_ids(apps)
    installed = dict(apps)
    apps = {k: v for k, v in apps.items() if k in allowed}
    if args.action == 'list':
        save_json([{k: a[k] for k in ('id', 'role', 'version', 'executable')} for a in apps.values()], None)
        return 0
    if args.action == 'capabilities':
        records = json.loads((ROOT / 'tool-capabilities.json').read_text())['applications']
        if ({r['id'] for r in records} != set(installed) or any(r['version'] != installed[r['id']]['version'] for r in records)):
            parser.error('Mappa capacità non allineata agli strumenti installati')
        records = [r for r in records if r['id'] in allowed]
        if args.app:
            record = next((r for r in records if r['id'] == args.app), None)
            if record is None or record['version'] != apps.get(args.app, {}).get('version'):
                parser.error('Mappa capacità assente o non allineata alla release installata')
            save_json({k:v for k,v in record.items() if k != 'catalog_ids' or args.all_commands}, None)
        else:
            save_json([{k:r[k] for k in ('id','version','choose_for','sources')} for r in records], None)
        return 0
    if args.app not in apps:
        parser.error('Applicazione sconosciuta: ' + args.app)
    app = apps[args.app]
    if args.action == 'help':
        reference = ROOT / 'reference' / args.app / 'help.txt'
        if reference.exists():
            print(reference.read_text(), end=''); return 0
        result = subprocess.run([app['executable'], '--help'], capture_output=True, text=True)
        print(result.stdout + result.stderr, end='')
        return 0 if 'usage' in (result.stdout + result.stderr).lower() else result.returncode
    if args.action in ('commands', 'run'):
        argv = app['registry_args'] if args.action == 'commands' else args.args
        if argv and argv[0] == '--':
            argv = argv[1:]
        return subprocess.run([app['executable'], *argv]).returncode
    session_timeout = getattr(args, 'timeout', None) or min(1200, max(1, int(float(os.environ.get('RIGHAVEN_JOB_DEADLINE', str(time.time() + 300))) - time.time() - 10)))
    session = McpSession([app['executable'], *app['mcp_args']], session_timeout)
    try:
        session.initialize()
        if args.action == 'tools':
            all_tools = []
            params = {}
            while True:
                result = session.call('tools/list', params)
                all_tools.extend(result.get('tools', []))
                if not result.get('nextCursor'):
                    break
                params = {'cursor': result['nextCursor']}
            save_json({'application': args.app, 'tools': all_tools}, args.out)
        else:
            steps = json.loads(Path(args.file).read_text())
            if not isinstance(steps, list) or not steps:
                raise ValueError('Il batch deve essere una lista JSON non vuota di chiamate')
            results = []
            for index, step in enumerate(steps):
                try:
                    if not isinstance(step, dict) or not isinstance(step.get('name'), str):
                        raise ValueError(f'Passaggio {index}: name obbligatorio')
                    arguments = resolve_references(step.get('arguments', {}), results)
                    if not isinstance(arguments, dict):
                        raise ValueError(f'Passaggio {index}: arguments deve essere un oggetto')
                    results.append(session.call('tools/call', {'name': step['name'], 'arguments': arguments}))
                except Exception as error:
                    if args.out:
                        save_json({'application': args.app, 'completed': len(results), 'failed_index': index,
                                   'results': results, 'error': str(error),
                                   'warning': 'Operazioni precedenti possono avere già modificato file. Non ripetere il batch alla cieca.'}, args.out)
                    raise
            save_json({'application': args.app, 'results': results}, args.out)
        return 0
    finally:
        session.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, TimeoutError, EOFError, KeyError, IndexError) as error:
        print(f'craft: {error}', file=sys.stderr)
        sys.exit(1)
