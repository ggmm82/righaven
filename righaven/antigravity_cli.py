"""Official agy subprocesses. No OAuth implementation or direct Google API calls."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

try:
    from .terminal_text import TerminalText
except ImportError:
    from terminal_text import TerminalText

TOKEN = 'antigravity-cli/antigravity-oauth-token'
AUTH_FILES = (TOKEN, 'antigravity-cli/auth.json')
ANSI = re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[>=]')


def copy_auth(source, destination):
    for filename in AUTH_FILES:
        path, target = Path(source) / filename, Path(destination) / filename
        if any(p.is_symlink() for p in (path, path.parent, target, target.parent)):
            raise ValueError('Link nelle credenziali non consentiti')
        if path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(path, target)
            target.chmod(0o600)


def cli_env():
    # Credentials and the model provider come exclusively from the panel.
    env = {k: v for k, v in os.environ.items() if k not in (
        'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'GOOGLE_GEMINI_BASE_URL',
        'AGY_LLM_GATEWAY_URL', 'AGY_ADC_AUTH', 'DBUS_SESSION_BUS_ADDRESS')}
    return {**env, 'AGY_CLI_DISABLE_AUTO_UPDATE': 'true', 'NO_BROWSER': 'true'}


def prepare_home(coordinator=False):
    root = Path.home() / '.gemini'
    settings = root / 'antigravity-cli/settings.json'
    settings.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    value = {'enableTelemetry': False, 'useG1Credits': False,
             'artifactReviewPolicy': 'always-proceed', 'showTips': False}
    if coordinator:
        value['permissions'] = {'deny': [a + '(*)' for a in (
            'command', 'unsandboxed', 'read_file', 'write_file', 'read_url', 'execute_url', 'mcp')]}
        agent = root / 'config/agents/skill-coordinator.md'
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_text('---\nname: skill-coordinator\ndescription: RigHaven coordinator without local tools\ntools: [finish]\nmainAgent: true\nsubagent: false\n---\n'
                         'Use the native finish tool to submit the requested structured decision. Do not use operational tools. '
                         'Only request tools offered in the supplied conversation; RigHaven executes them.\n')
    settings.write_text(json.dumps(value))
    settings.chmod(0o600)
    return root


def models():
    result = subprocess.run(['agy', 'models'], env=cli_env(), capture_output=True,
                            text=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Antigravity: completa il login Google o verifica la disponibilità dell’account')
    entries = []
    for line in ANSI.sub('', result.stdout).splitlines():
        match = re.fullmatch(r'\s*([a-z0-9][a-z0-9._:/-]+)\s+(.+?)\s*', line)
        if match:
            entries.append({'id': match[1], 'label': match[2], 'default': False})
    if not entries:
        raise RuntimeError('Elenco modelli Antigravity non riconosciuto; nessun modello inventato')
    return entries


def result_envelope(output):
    events = [json.loads(line) for line in output.splitlines() if line.strip()]
    results = [event['result'] for event in events if event.get('event') == 'result']
    if len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError('Risultato Antigravity mancante o ambiguo')
    return results[0]


def result_error(envelope):
    """Use the reported cause; generic guidance is not proof of exhausted quota."""
    error = envelope.get('error')
    if isinstance(error, dict):
        error = error.get('message') or error.get('code')
    if isinstance(error, str) and error.strip():
        return 'Antigravity: ' + error.strip()[:1200]
    return 'Antigravity: completamento non confermato dalla CLI (stato: ' + str(envelope.get('status', 'assente'))[:80] + '). Ispeziona i file salvati e il dettaglio dell’esecuzione.'


def generate(payload):
    prepare_home(coordinator=True)
    schema = payload['schema']
    working = Path('/tmp/skill-coordinator')
    working.mkdir(exist_ok=True, mode=0o700)
    schema_file = working / 'decision-schema.json'
    schema_file.write_text(json.dumps(schema))
    # Stdin avoids argv limits and keeps full conversation/prompt out of process listings.
    args = ['agy', '--input-format', 'stream-json', '--output-format', 'stream-json', '--disable-slash-commands',
            '--agent', 'skill-coordinator', '--json-schema', str(schema_file),
            '--print-timeout', '25m']
    if payload['model'] != 'auto':
        args += ['--model', payload['model']]
    result = subprocess.run(args, input=json.dumps({'event': 'user', 'message': {'content': payload['prompt']}}) + '\n', env=cli_env(),
                            capture_output=True, text=True, timeout=1530, cwd=working)
    try:
        envelope = result_envelope(result.stdout)
    except ValueError:
        raise RuntimeError('Risposta JSON Antigravity non valida') from None
    if result.returncode or envelope.get('status') != 'SUCCESS':
        raise RuntimeError(result_error(envelope))
    decision = envelope.get('structured_output')
    if not isinstance(decision, dict):
        raise RuntimeError('Antigravity non ha restituito la decisione strutturata')
    return {**decision, 'usage': envelope.get('usage', {})}


def login():
    """Expose the CLI's remote Google login through a bounded, plain-text terminal."""
    import fcntl
    import pty
    import select
    import signal
    import struct
    import time
    root = prepare_home()
    master, slave = pty.openpty()
    # The native TUI wraps authorization URLs at the terminal width. Keep the
    # complete URL on one line so the web panel never links a truncated URL.
    fcntl.ioctl(slave, __import__('termios').TIOCSWINSZ, struct.pack('HHHH', 100, 2048, 0, 0))
    env = {**cli_env(), 'SSH_CONNECTION': '127.0.0.1 1 127.0.0.1 22', 'TERM': 'xterm-256color'}
    child = subprocess.Popen(['agy'], stdin=slave, stdout=slave, stderr=slave,
                             env=env, start_new_session=True)
    os.close(slave)
    started = time.monotonic()
    selected, buffer, token_seen = False, '', None
    terminal = TerminalText()
    try:
        while child.poll() is None and time.monotonic() - started < 570:
            ready, _, _ = select.select([master, sys.stdin], [], [], .2)
            if master in ready:
                try:
                    data = os.read(master, 16384)
                except OSError:
                    break
                text = terminal.feed(data)
                buffer = (buffer + text)[-64000:]
                # Emit only CLI login text; never print cached credentials.
                print(text, end='', flush=True)
                if any(message in buffer.lower() for message in (
                        'got an error:', 'token exchange failed:', 'invalid_grant')):
                    raise RuntimeError('Codice Google non valido o scaduto. Avvia un nuovo accesso e usa soltanto il suo codice.')
                if not selected and 'Select login method:' in buffer:
                    os.write(master, b'\r')  # Official default: Google OAuth.
                    selected = True
            if sys.stdin in ready:
                data = os.read(sys.stdin.fileno(), 4096)
                if not data:
                    break
                os.write(master, data.replace(b'\n', b'\r'))
            if (root / TOKEN).is_file():
                token_seen = token_seen or time.monotonic()
                if time.monotonic() - token_seen > 2:
                    break
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        os.close(master)
    if not (root / TOKEN).is_file():
        raise RuntimeError('Accesso Google non completato. Avvia un nuovo accesso dal pannello.')
    # Keep a successful OAuth exchange even when catalog verification fails.
    Path('/credentials/antigravity-account.json').unlink(missing_ok=True)
    copy_auth(root, '/credentials')
    try:
        available = models()  # Official authenticated catalog, no generation.
    except RuntimeError as error:
        raise RuntimeError('Accesso Google ricevuto, ma verifica modelli fallita. ' + str(error)) from None
    marker = Path('/credentials/antigravity-account.json')
    marker.write_text(json.dumps({'models': available, 'verified_by': 'agy models'}))
    marker.chmod(0o600)
    print('\nAccount Antigravity collegato. Salva e attiva la squadra.', flush=True)


def main():
    root = prepare_home()
    if sys.argv[1] == '--login':
        login()
        return
    copy_auth('/credentials', root)
    try:
        if sys.argv[1] == '--models':
            print(json.dumps({'ok': True, 'models': models()}))
        else:
            print(json.dumps({'ok': True, 'response': generate(json.loads(Path(sys.argv[1]).read_text()))}))
    finally:
        copy_auth(root, '/credentials')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Only our fixed diagnostic messages may cross the login boundary.
        message = str(error) if isinstance(error, RuntimeError) else 'Antigravity: verifica login Google, modello e quota'
        print(json.dumps({'ok': False, 'error': message}))
        sys.exit(1)
