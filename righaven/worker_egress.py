"""Internal network and egress proxy for assignment workers (allowlist mode).

The proxy runs from the worker software image on both the default bridge and
an internal network; workers join only the internal network, so the proxy is
their single way out. Each job receives its own token and grant file.
"""
import json
import secrets
import subprocess
import threading

from .state import STATE

NETWORK = 'righaven-egress'
PROXY = 'righaven-egress-proxy'
PORT = 3128
_LOCK = threading.Lock()


def folders():
    root = STATE / 'egress'
    rules, log = root / 'rules', root / 'log'
    for folder, permissions in ((root, 0o755), (rules, 0o755), (log, 0o733)):
        folder.mkdir(parents=True, exist_ok=True)
        folder.chmod(permissions)
    return rules, log


def _run(*arguments, timeout=60):
    return subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=timeout)


def ensure():
    """Create the internal network and start the proxy when missing; idempotent."""
    from .docker_runtime import IMAGE, LABEL, OWNER, mount, docker, runtime_arguments
    with _LOCK:
        rules, log = folders()
        if _run('network', 'inspect', NETWORK).returncode:
            docker('network', 'create', '--internal', '--label', f'{LABEL}={OWNER}', NETWORK)
        running = _run('inspect', '--format', '{{.State.Running}}', PROXY)
        if running.stdout.strip() != 'true':
            _run('rm', '-f', PROXY, timeout=30)
            docker('run', '-d', '--name', PROXY, '--label', f'{LABEL}={OWNER}', '--restart', 'unless-stopped',
                   '--init', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--read-only',
                   '--pids-limit=128', '--memory=192m', '--cpus=0.5', '--network=bridge',
                   '--mount', mount(rules, '/egress/rules', True), '--mount', mount(log, '/egress/log'),
                   '--env', 'RIGHAVEN_EGRESS_RULES=/egress/rules', '--env', 'RIGHAVEN_EGRESS_LOG=/egress/log',
                   *runtime_arguments(), IMAGE, 'python3', '/opt/righaven-worker/egress_proxy.py', timeout=120)
        networks = _run('inspect', '--format', '{{json .NetworkSettings.Networks}}', PROXY).stdout
        if NETWORK not in (networks or ''):
            docker('network', 'connect', NETWORK, PROXY)


class Grant:
    """One job's permission to leave the internal network."""

    def __init__(self, job, domains):
        self.job, self.domains = job, list(domains)
        self.token = secrets.token_hex(16)
        self.rules, self.log = folders()
        path = self.rules / (self.token + '.json')
        path.write_text(json.dumps({'job': job, 'domains': self.domains}))
        path.chmod(0o644)

    def arguments(self, args):
        """Worker docker-run arguments moved to the internal network, with proxy settings."""
        proxy = f'http://{self.job}:{self.token}@{PROXY}:{PORT}'
        moved = [f'--network={NETWORK}' if item == '--network=bridge' else item for item in args]
        if f'--network={NETWORK}' not in moved:
            raise ValueError('Worker network not found in the container arguments')
        position = moved.index(f'--network={NETWORK}') + 1
        environment = []
        for name in ('HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy'):
            environment += ['--env', f'{name}={proxy}']
        environment += ['--env', 'NO_PROXY=localhost,127.0.0.1', '--env', 'no_proxy=localhost,127.0.0.1',
                        '--env', 'NODE_USE_ENV_PROXY=1']
        return moved[:position] + environment + moved[position:]

    def close(self):
        """Refused connections of this job; the grant stops working."""
        (self.rules / (self.token + '.json')).unlink(missing_ok=True)
        path = self.log / (self.token + '.jsonl')
        refused = []
        try:
            for line in path.read_text().splitlines()[-200:]:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    refused.append({k: event.get(k) for k in ('at', 'host', 'port', 'reason')})
        except OSError:
            pass
        path.unlink(missing_ok=True)
        return refused


def summary(refused):
    """Distinct refused destinations, most frequent first."""
    counts = {}
    for event in refused:
        key = f"{event.get('host')}:{event.get('port')}"
        counts[key] = counts.get(key, 0) + 1
    return [{'destination': key, 'attempts': value} for key, value in sorted(counts.items(), key=lambda item: -item[1])][:20]
