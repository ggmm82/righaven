"""Refresh CLI-owned OAuth via the official app-server protocol, without generation."""
import json
import queue
import subprocess
import threading
import sys


def refresh(action='refresh'):
    process = subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    incoming = queue.Queue()
    def read():
        try:
            for line in process.stdout:
                incoming.put(json.loads(line))
        finally:
            incoming.put(None)
    threading.Thread(target=read, daemon=True).start()
    def send(value):
        process.stdin.write(json.dumps(value) + '\n')
        process.stdin.flush()
    def result(identifier):
        while True:
            message = incoming.get(timeout=45)
            if message is None or message.get('error'):
                raise RuntimeError('Ricollega Codex in La tua squadra')
            if message.get('id') == identifier:
                return message['result']
    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'skill-harness', 'version': '0.1.0'}}})
        result(1)
        send({'method': 'initialized'})
        if action == 'models':
            models, cursor, identifier = [], None, 2
            while True:
                send({'id': identifier, 'method': 'model/list', 'params': {'limit': 100, 'cursor': cursor}})
                page = result(identifier)
                models.extend({'id': item['model'], 'label': item['displayName'],
                               'default': item.get('isDefault', False)} for item in page['data'] if not item.get('hidden'))
                cursor = page.get('nextCursor')
                if not cursor:
                    return models
                identifier += 1
                if identifier > 20:
                    raise RuntimeError('Catalogo Codex incompleto')
        send({'id': 2, 'method': 'account/read', 'params': {'refreshToken': True}})
        account = result(2).get('account')
        if not account or account.get('type') != 'chatgpt':
            raise RuntimeError('Ricollega Codex in La tua squadra')
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


if __name__ == '__main__':
    try:
        models = refresh('models' if '--models' in sys.argv else 'refresh')
        print(json.dumps({'ok': True, **({'models': models} if models is not None else {})}))
    except Exception:
        print('{"ok": false, "error": "Ricollega Codex in La tua squadra"}')
        raise SystemExit(1)
