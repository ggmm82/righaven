#!/usr/bin/env python3
"""Real-container check of worker egress allowlisting (RIGHAVEN_WORKER_EGRESS=allowlist).

A worker on the internal network must reach a granted domain only through the
egress proxy, be refused for any other domain (with the refusal logged) and
have no direct route to the Internet. Uses the same flags as worker_egress.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile

NETWORK = 'righaven-egress-check'
PROXY = 'righaven-egress-proxy-check'
PROBE = r'''
import json, socket, urllib.error, urllib.request
result = {}
def fetch(url):
    try:
        return urllib.request.urlopen(url, timeout=20).status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError) as error:
        return type(getattr(error, "reason", error)).__name__ + ": " + str(getattr(error, "reason", error))[:120]
result["granted"] = fetch("https://github.com/")
result["refused"] = fetch("https://example.com/")
try:
    socket.create_connection(("1.1.1.1", 443), timeout=5).close()
    result["direct"] = "connected"
except OSError as error:
    result["direct"] = type(error).__name__
print(json.dumps(result))
'''


def docker(*arguments, check=True):
    return subprocess.run(['docker', *arguments], capture_output=True, text=True, check=check, timeout=300)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='righaven-sandbox:0.1.0')
    image = parser.parse_args().image
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='righaven-egress-') as folder:
        rules, log = Path(folder) / 'rules', Path(folder) / 'log'
        rules.mkdir(mode=0o755); log.mkdir(); log.chmod(0o733)
        token, job = secrets.token_hex(16), 'rh-job-egress-check'
        (rules / (token + '.json')).write_text(json.dumps({'job': job, 'domains': ['github.com']}))
        (rules / (token + '.json')).chmod(0o644)
        docker('rm', '-f', PROXY, check=False); docker('network', 'rm', NETWORK, check=False)
        try:
            docker('network', 'create', '--internal', NETWORK)
            docker('run', '-d', '--name', PROXY, '--init', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--read-only',
                   '--pids-limit=128', '--memory=192m', '--network=bridge',
                   '--mount', f'type=bind,src={rules},dst=/egress/rules,readonly', '--mount', f'type=bind,src={log},dst=/egress/log',
                   '--mount', f'type=bind,src={repo / "righaven/egress_proxy.py"},dst=/opt/righaven-worker/egress_proxy.py,readonly',
                   '--env', 'RIGHAVEN_EGRESS_RULES=/egress/rules', '--env', 'RIGHAVEN_EGRESS_LOG=/egress/log',
                   '--entrypoint', 'python3', image, '/opt/righaven-worker/egress_proxy.py')
            docker('network', 'connect', NETWORK, PROXY)
            proxy = f'http://{job}:{token}@{PROXY}:3128'
            probe = docker('run', '--rm', '--init', '--cap-drop=ALL', '--security-opt=no-new-privileges', f'--network={NETWORK}',
                           '--env', f'HTTPS_PROXY={proxy}', '--env', f'HTTP_PROXY={proxy}', '--entrypoint', 'python3', image, '-c', PROBE)
            result = json.loads(probe.stdout.strip().splitlines()[-1])
            refused = [json.loads(line) for line in (log / (token + '.jsonl')).read_text().splitlines()] if (log / (token + '.jsonl')).exists() else []
        finally:
            logs = docker('logs', PROXY, check=False)
            docker('rm', '-f', PROXY, check=False); docker('network', 'rm', NETWORK, check=False)
        assert isinstance(result['granted'], int) and result['granted'] < 500, (result, logs.stdout[-2000:], logs.stderr[-2000:])
        assert 'Tunnel connection failed: 403' in str(result['refused']) or result['refused'] == 403, result
        assert result['direct'] != 'connected', result
        assert [(e['host'], e['reason']) for e in refused] == [('example.com', 'domain')], refused
        print('Worker egress OK: granted domain through the proxy, other domain refused and logged, no direct route:', result)


if __name__ == '__main__':
    main()
