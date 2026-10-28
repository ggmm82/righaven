"""Pinned official Codex app-server transport and bounded native image handoff.

Only protocol item events identify generated assets. Never scan the auth home,
store wire transcripts, or infer image generation from assistant claims.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import struct
import subprocess
import tempfile
import threading
import time
import zlib

try:
    from .cli_runner import ProviderSilence
except ImportError:
    from cli_runner import ProviderSilence

MAX_IMAGE = 32 * 1024 * 1024
MAX_FRAME = 48 * 1024 * 1024
STARTUP_TIMEOUT = 60


def safe_path(path, root):
    path, root = Path(path), Path(root)
    if not path.is_absolute() or '..' in path.parts or not path.is_relative_to(root):
        raise ValueError('Asset generato fuori dalla cartella autorizzata')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Link negli asset generati non consentiti')
    return path


def png_info(data):
    if len(data) > MAX_IMAGE or data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Asset nativo non PNG o troppo grande')
    offset, dimensions, image_data, ended = 8, None, False, False
    while offset + 12 <= len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise ValueError('PNG troncato')
        payload = data[offset + 8:end - 4]
        if zlib.crc32(kind + payload) & 0xffffffff != struct.unpack('>I', data[end - 4:end])[0]:
            raise ValueError('CRC PNG non valido')
        if offset == 8:
            if kind != b'IHDR' or size != 13:
                raise ValueError('Intestazione PNG non valida')
            dimensions = struct.unpack('>II', payload[:8])
            if not all(0 < n <= 32768 for n in dimensions) or dimensions[0] * dimensions[1] > 100000000:
                raise ValueError('Dimensioni PNG non valide')
        if kind == b'IDAT':
            image_data = True
        if kind == b'IEND':
            ended = size == 0 and end == len(data)
            break
        offset = end
    if not dimensions or not image_data or not ended:
        raise ValueError('PNG incompleto')
    return dimensions


def export_image(item, output, codex_home):
    """Copy one reported PNG byte-for-byte, preserving embedded C2PA metadata."""
    if item.get('status') != 'completed' or item.get('failure'):
        failure = item.get('failure') or {}
        if failure.get('type') == 'usageLimitExceeded':
            raise RuntimeError('Quota della generazione nativa esaurita; i file già salvati sono conservati')
        raise RuntimeError('Generazione nativa non completata; i file già salvati sono conservati')
    source = item.get('savedPath')
    if not isinstance(source, str):
        raise ValueError('Codex non ha restituito il percorso dell’immagine generata')
    root = Path(codex_home) / 'generated_images'
    source = safe_path(source, root)
    if not source.is_file() or source.stat().st_size > MAX_IMAGE:
        raise ValueError('Immagine generata assente o troppo grande')
    with source.open('rb') as stream:
        data = stream.read(MAX_IMAGE + 1)
    width, height = png_info(data)
    digest = hashlib.sha256(data).hexdigest()
    output = Path(output)
    target = safe_path(output / 'generated_images' / (digest + '.png'), output)
    target.parent.mkdir(exist_ok=True)
    # Refuse overwrites and symlinks; duplicate identical events are idempotent.
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Asset esportato modificato')
    else:
        with target.open('xb') as stream:
            stream.write(data)
    record = {'tool': 'image_gen.imagegen', 'transport': 'codex_app_server', 'item_id': item.get('id'),
              'status': 'completed', 'path': str(target), 'sha256': digest, 'bytes': len(data),
              'width': width, 'height': height, 'format': 'PNG',
              'revised_prompt': item.get('revisedPrompt'), 'transparent_background': item.get('transparentBackground'),
              'limits': ['Prompt originario, seed e modello immagine non esposti da questo evento.',
                         'Asset raster: non è un sorgente vettoriale o un documento a livelli.',
                         'Verifica strutturale PNG; qualità visiva e firma C2PA non verificate dal trasferimento.']}
    manifest = safe_path(output / 'work' / ('imagegen-' + digest + '.json'), output)
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    manifest.chmod(0o600)
    return record


def event_for_progress(method, params):
    """Adapt actual camelCase app-server items to the existing private observer."""
    if method in ('turn/started', 'turn/completed'):
        return {'type': method.replace('/', '.')}
    if method not in ('item/started', 'item/completed'):
        return None
    item = params.get('item') or {}
    kind = item.get('type')
    mapped = {'commandExecution': 'command_execution', 'mcpToolCall': 'mcp_tool_call',
              'imageGeneration': 'image_generation', 'webSearch': 'web_search'}.get(kind)
    if not mapped:
        return None
    return {'type': method.replace('/', '.'), 'item': {'type': mapped,
            'id': item.get('id'), 'command': item.get('command'), 'exit_code': item.get('exitCode'), 'tool': item.get('tool'),
            'duration_ms': item.get('durationMs'), 'output': item.get('aggregatedOutput')}}


def run(model, prompt, output, timeout, progress, *, env=None, executable='codex', image_generation=True, preflight=None):
    env = dict(env if env is not None else os.environ)
    env['RIGHAVEN_OUTPUT_DIR'] = str(output)
    codex_home = Path(env.get('CODEX_HOME', str(Path.home() / '.codex')))
    args = [executable, '--enable' if image_generation else '--disable', 'image_generation',
            'app-server', '--listen', 'stdio://']
    deadline = time.monotonic() + timeout
    startup_deadline = min(deadline, time.monotonic() + STARTUP_TIMEOUT)
    turn_accepted = False
    thread_id, metadata_repairs = None, 0
    events = queue.Queue(maxsize=8)
    messages, active_tools = [], set()
    last_event = time.monotonic()
    budget = getattr(progress, 'model_wait_seconds', 0)
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(args, cwd=output, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
        stop = threading.Event()
        def reader():
            try:
                while not stop.is_set():
                    line = process.stdout.readline(MAX_FRAME + 1)
                    if not line:
                        break
                    if len(line) > MAX_FRAME or not line.endswith(b'\n'):
                        raise ValueError('Evento Codex oltre il limite supportato')
                    event = json.loads(line)
                    item = (event.get('params') or {}).get('item')
                    if isinstance(item, dict) and item.get('type') == 'imageGeneration':
                        item.pop('result', None)  # Base64 is never retained or logged; savedPath is authoritative.
                    while not stop.is_set():
                        try:
                            events.put(event, timeout=.2)
                            break
                        except queue.Full:
                            pass
            except (ValueError, OSError) as exc:
                events.put({'_reader_error': type(exc).__name__}, timeout=1)
            finally:
                try:
                    events.put(None, timeout=1)
                except queue.Full:
                    pass
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        def send(value):
            process.stdin.write((json.dumps(value) + '\n').encode())
            process.stdin.flush()
        def request(ident, method, params):
            send({'id': ident, 'method': method, 'params': params})
        try:
            progress.emit('preparing', 'Avvio Codex e preparazione del collegamento')
            request(1, 'initialize', {'clientInfo': {'name': 'righaven_harness', 'version': '1'},
                                    'capabilities': {'experimentalApi': True}})
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired('codex', timeout)
                if not turn_accepted and time.monotonic() >= startup_deadline:
                    raise ProviderSilence('Budget di avvio Codex esaurito: la CLI non ha confermato l’accettazione dell’incarico; file salvati conservati')
                try:
                    event = events.get(timeout=min(.25, remaining))
                except queue.Empty:
                    if budget and not active_tools and time.monotonic() - last_event > budget:
                        raise ProviderSilence('Budget di attesa del modello esaurito senza nuovi eventi')
                    continue
                if event is None:
                    raise RuntimeError('Codex app-server terminato prima della conclusione del turno')
                if '_reader_error' in event:
                    raise RuntimeError('Evento Codex non valido o troppo grande')
                last_event = time.monotonic()
                progress.model_signal()
                if event.get('error'):
                    raise RuntimeError('Codex app-server: ' + str(event['error'].get('message', 'errore protocollo'))[:1000])
                ident, method, params = event.get('id'), event.get('method'), event.get('params') or {}
                if method and ident is not None:
                    # This headless worker must never wait forever for an interactive request.
                    send({'id': ident, 'error': {'code': -32601, 'message': 'Interazione non disponibile nel worker; comunica il limite al coordinatore'}})
                    continue
                if ident == 1:
                    send({'method': 'initialized'})
                    config = {'cwd': str(output), 'approvalPolicy': 'never', 'sandbox': 'danger-full-access',
                              'ephemeral': True, 'serviceName': 'chatgpt_cca'}
                    if model:
                        config['model'] = model
                    request(2, 'thread/start', config)
                elif ident == 2:
                    thread_id = event['result']['thread']['id']
                    request(3, 'turn/start', {'threadId': thread_id,
                            'input': [{'type': 'text', 'text': prompt, 'text_elements': []}]})
                if ident in (3, 4) or method == 'turn/started':
                    turn_accepted = True
                    if not active_tools:
                        progress.emit('waiting_model', 'Incarico accettato da Codex; attendo la risposta del modello')
                if method in ('item/started', 'item/completed'):
                    item = params.get('item') or {}
                    key, kind = item.get('id'), item.get('type')
                    if kind in ('commandExecution', 'mcpToolCall', 'imageGeneration', 'webSearch', 'dynamicToolCall'):
                        if method == 'item/started':
                            active_tools.add(key)
                        else:
                            active_tools.discard(key)
                    if method == 'item/completed' and kind == 'imageGeneration':
                        if not image_generation:
                            raise RuntimeError('Generazione immagini vietata dalla scelta vettoriale dell’utente')
                        export_image(item, output, codex_home)
                    if method == 'item/completed' and kind == 'agentMessage':
                        text = item.get('text')
                        if isinstance(text, str):
                            messages.append(text[:64000])
                normalized = event_for_progress(method, params)
                if normalized:
                    progress.cli_event('codex', normalized)
                if method == 'turn/completed':
                    turn = params.get('turn') or {}
                    if turn.get('status') != 'completed':
                        error = turn.get('error') or {}
                        kind = error.get('codexErrorInfo')
                        category = {'unauthorized': 'Authentication required: ',
                                    'usageLimitExceeded': 'Usage limit exceeded: '}.get(kind, '') if isinstance(kind, str) else ''
                        raise RuntimeError('Codex: ' + category + str(error.get('message') or turn.get('status') or 'turno non concluso')[:1000])
                    if preflight is not None:
                        try:
                            preflight()
                        except (OSError, ValueError) as error:
                            if metadata_repairs or deadline - time.monotonic() < 15:
                                raise
                            metadata_repairs += 1
                            messages.clear()
                            progress.emit('checking', 'Correggo i metadati nella stessa sandbox; prodotti conservati')
                            request(4, 'turn/start', {'threadId':thread_id, 'input':[{'type':'text', 'text':
                                'Il preflight della consegna non è superato: ' + str(error)[:2000] +
                                '. Correggi soltanto handoff.json e i riferimenti ai file già esistenti. '
                                'Non rigenerare o cambiare il prodotto, non promuovere failed/not_run a passed. '
                                'Esegui /usr/bin/python3 /opt/righaven-worker/handoff.py validate "' + str(output) +
                                '" e concludi. Un solo recupero nello stesso incarico e nel budget residuo.', 'text_elements':[]}]})
                            continue
                    return '\n'.join(messages[-4:])
        finally:
            stop.set()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            process.wait()
            process.stdin.close()
            process.stdout.close()
            thread.join(timeout=2)
