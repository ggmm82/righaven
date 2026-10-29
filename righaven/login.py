"""CLI-owned browser authentication, displayed through a bounded pseudo-terminal."""
import os
import json
import pty
import select
import signal
import subprocess
import threading
import time
import uuid

from .docker_runtime import IMAGE, EXECUTION_LOCK, base_arguments, mount, close_provider as remove, runtime_arguments
from .state import STATE, credential_dir
from .terminal_text import TerminalText, authorization_url

SESSIONS = {}


def login_command(engine):
    if engine == 'gemini':
        # Official CLI auth only: interactive OAuth, no paid generation or /quit.
        return ['python3', '/opt/righaven-worker/antigravity_cli.py', '--login']
    if engine == 'claude':return ['claude','auth','login']
    if engine == 'codex':
        return ['codex', 'login', '--device-auth']
    raise ValueError('Motore sconosciuto')


class LoginSession:
    def __init__(self, engine):
        if engine not in ('codex', 'gemini','claude'):
            raise ValueError('Motore sconosciuto')
        if not EXECUTION_LOCK.acquire(blocking=False):
            raise RuntimeError('Un lavoro o un login è già attivo')
        try:
            self._start(engine)
        except Exception:
            EXECUTION_LOCK.release()
            raise

    def _start(self, engine):
        self.id = uuid.uuid4().hex
        self.engine = engine
        self.name = 'skill-login-' + self.id[:12]
        self.text = ''
        self._terminal = TerminalText()
        self.input_sent = False
        self.returncode = None
        self.closed = False
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self.started = time.monotonic()
        credentials = credential_dir(engine)
        cli = login_command(engine)
        master, slave = pty.openpty()
        self.fd = master
        try:
            installation = (STATE / 'installation-id').read_text().strip()
            from .docker_runtime import provider_image
            selected_image=provider_image(engine,claim=self.name)
            args = base_arguments(self.name) + runtime_arguments() + ['-it', '--label',
                    f'org.righaven.harness.installation={installation}', '--mount',
                    mount(credentials, '/root/.codex' if engine == 'codex' else '/credentials'),
                    *(['--env','CLAUDE_CONFIG_DIR=/credentials','--env','DISABLE_AUTOUPDATER=1'] if engine=='claude' else []),selected_image, *cli]
            self.process = subprocess.Popen(['docker', *args], stdin=slave, stdout=slave,
                                            stderr=slave, start_new_session=True)
        except Exception:
            os.close(master)
            remove(self.name)
            raise
        finally:
            os.close(slave)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                if self.process.poll() is None and (self._cancel.is_set() or time.monotonic() - self.started > 600):
                    self._terminate()
                    break
                ready, _, _ = select.select([self.fd], [], [], 0.3)
                if ready:
                    try:
                        chunk = os.read(self.fd, 8192)
                    except OSError:
                        break
                    if not chunk:
                        break
                    with self._lock:
                        self.text = (self.text + self._terminal.feed(chunk))[-64000:]
                elif self.process.poll() is not None:
                    break
            self.returncode = self.process.wait(timeout=10)
        finally:
            if self.process.poll() is None:
                self._terminate()
            remove(self.name)
            os.close(self.fd)
            self.closed = True
            EXECUTION_LOCK.release()

    def _terminate(self):
        remove(self.name)
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)

    def public(self):
        with self._lock:
            error = None
            for line in reversed(self.text.splitlines()):
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict) and value.get('ok') is False:
                    error = value.get('error')
                    break
            return {'id': self.id, 'engine': self.engine, 'text': self.text,
                    'authorization_url': authorization_url(self.text, self.engine),
                    'input_sent': self.input_sent, 'error': error,
                    'finished': self.closed, 'returncode': self.returncode}

    def write(self, text):
        if self.closed or self.process.poll() is not None:
            raise ValueError('Sessione terminata')
        if self.input_sent:
            raise ValueError('Codice già inviato: attendi l’esito della verifica')
        if len(text) > 4096 or '\x00' in text:
            raise ValueError('Input non valido')
        text = text.strip()
        if not text:
            raise ValueError('Incolla il codice restituito dal provider')
        os.write(self.fd, (text + '\n').encode())
        self.input_sent = True

    def cancel(self):
        self._cancel.set()


def start(engine):
    for session in SESSIONS.values():
        if not session.closed and session.engine == engine:
            return session.public()
    # Finished terminal transcripts are short-lived and never persisted to logs.
    for identifier, session in list(SESSIONS.items()):
        if session.closed and time.monotonic() - session.started > 600:
            SESSIONS.pop(identifier, None)
    session = LoginSession(engine)
    SESSIONS[session.id] = session
    return session.public()
