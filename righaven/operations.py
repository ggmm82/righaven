"""Persistent supervision for expensive tools: one process group per stable key."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

try:
    from .resource_usage import snapshot
except ImportError:
    from resource_usage import snapshot


def write(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value))
    os.replace(temp, path)


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[19] if fields[0] != 'Z' else None
    except (OSError, IndexError):
        return None


def folder(root, key):
    path = Path(root).resolve() / 'work/operations' / hashlib.sha256(key.encode()).hexdigest()[:24]
    path.mkdir(parents=True, exist_ok=True)
    return path


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # Also kill grandchildren left alive after the parent exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def supervise(argv, root, key, *, timeout=1200, label='Elaborazione dello strumento', estimate_seconds=None):
    if os.environ.get('RIGHAVEN_JOB_DEADLINE'):
        timeout = min(timeout, float(os.environ['RIGHAVEN_JOB_DEADLINE']) - time.time() - 10)
    if timeout <= 0:
        raise subprocess.TimeoutExpired(argv[0], timeout)
    path = folder(root, key)
    shared = path.parent / 'active.json'
    with (path.parent / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Operazione già attiva: non avviare una copia. Stato: ' + str(path / 'status.json')) from None
        status_file = path / 'status.json'
        old = json.loads(shared.read_text()) if shared.exists() else {}
        if old.get('pid') and old.get('process_identity') and identity(old['pid']) == old['process_identity']:
            raise RuntimeError('Processo precedente ancora attivo: attendere e leggere ' + str(status_file))
        started = time.monotonic()
        before = snapshot()
        value = {'id': path.name, 'label': label[:100], 'state': 'running', 'started_at': time.time(),
                 'elapsed_seconds': 0, 'progress': None, 'returncode': None, 'oom_kills': 0}
        if estimate_seconds is not None:
            value['estimate_seconds'] = estimate_seconds
        previous_handlers = {}
        process = None
        log_path = path / 'log.txt'
        try:
            with log_path.open('wb') as output:
                process = subprocess.Popen(argv, cwd=root, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                value.update(pid=process.pid, process_identity=identity(process.pid))
                write(status_file, value)
                write(shared, value)
                def interrupted(signum, frame):
                    raise InterruptedError('Operazione interrotta; processi figli arrestati')
                import threading
                if threading.current_thread() is threading.main_thread():
                    for sig in (signal.SIGTERM, signal.SIGINT):
                        previous_handlers[sig] = signal.signal(sig, interrupted)
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    usage = snapshot()
                    value.update(elapsed_seconds=round(elapsed, 1), updated_at=time.time(),
                                 memory_bytes=usage['memory_bytes'])
                    with log_path.open('rb') as reader:
                        reader.seek(max(0, log_path.stat().st_size - 12000))
                        tail = reader.read().decode('utf-8', 'replace')
                    samples = list(re.finditer(r'Sample\s+(\d+)\s*/\s*(\d+)', tail))
                    if samples:
                        done, total = map(int, samples[-1].groups())
                        if total > 0:
                            value['progress'] = {'done': done, 'total': total, 'unit': 'campioni'}
                    write(status_file, value)
                    if elapsed >= timeout:
                        raise subprocess.TimeoutExpired(argv[0], timeout)
                    time.sleep(.25)
                value.update(state='completed' if process.returncode == 0 else 'failed', returncode=process.returncode)
        except BaseException:
            value['state'] = 'interrupted'
            raise
        finally:
            if process is not None:
                stop_group(process)
            after = snapshot()
            value.update(elapsed_seconds=round(time.monotonic() - started, 1), updated_at=time.time(),
                         memory_bytes=after['memory_bytes'])
            if after['oom_kills'] is not None and before['oom_kills'] is not None:
                value['oom_kills'] = max(0, int(after['oom_kills'] - before['oom_kills']))
            if value['oom_kills']:
                value['state'] = 'out_of_memory'
            write(status_file, value)
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
        with log_path.open('rb') as stream:
            stream.seek(max(0, log_path.stat().st_size - 16000))
            tail = stream.read().decode('utf-8', 'replace')
        return subprocess.CompletedProcess(argv, process.returncode, tail, ''), value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True, help='Stable name for this exact export and its inputs; change for a different version')
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--label', default='Elaborazione dello strumento')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not argv or not 1 <= args.timeout <= 1500:
        parser.error('Comando obbligatorio e timeout fra 1 e 1500 secondi')
    result, status = supervise(argv, os.environ['RIGHAVEN_OUTPUT_DIR'], args.key, timeout=args.timeout, label=args.label)
    print(json.dumps({'operation': status, 'output_tail': result.stdout}, ensure_ascii=False))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
