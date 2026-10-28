"""DeepSeek API transport and bounded tool loop used by the real worker."""
import json
import os
import tempfile
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

BASE_URL = 'https://api.deepseek.com'
MAX_TURNS = 64

try:
    from .handoff import HANDOFF_SCHEMA, validate_handoff
except ImportError:
    from handoff import HANDOFF_SCHEMA, validate_handoff


def request(key, path, payload=None, timeout=120):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Provider response bodies can contain reflected request information.
        if error.code == 401:
            raise ValueError('Chiave DeepSeek rifiutata') from None
        raise RuntimeError(f'DeepSeek HTTP {error.code}') from None
    except (OSError, ValueError) as error:
        if isinstance(error, ValueError) and str(error) == 'Chiave DeepSeek rifiutata':
            raise
        raise RuntimeError('Connessione DeepSeek non riuscita') from None


def models(key):
    result = request(key, '/models', timeout=30)
    return [m['id'] for m in result['data'] if isinstance(m.get('id'), str)]



HANDOFF_TOOL = {'type': 'function', 'function': {
    'name': 'submit_handoff',
    'description': 'Consegna i file già prodotti. Scrive handoff.json e verifica percorsi e file. Includi sorgenti modificabili e delivery con formato, app di apertura, modificabilità e riapertura per ogni output. Riporta soltanto controlli effettivi; usa not_run per quelli non svolti.',
    'parameters': HANDOFF_SCHEMA}}

PROGRESS_TOOL = {'type': 'function', 'function': {
    'name': 'report_progress',
    'description': 'Mostra all’utente un breve aggiornamento operativo: obiettivo, azione scelta o verifica. Non includere ragionamenti interni, credenziali, prompt o percentuali inventate.',
    'parameters': {'type': 'object', 'properties': {
        'phase': {'type': 'string', 'enum': ['planning', 'creating', 'exporting', 'checking', 'finalizing']},
        'summary': {'type': 'string', 'maxLength': 280}}, 'required': ['phase', 'summary'],
        'additionalProperties': False}}}


def submit_handoff(output_dir, value):
    """Finalize through a checked tool instead of asking the model to quote shell JSON."""
    path = output_dir / 'handoff.json'
    fd, temporary = tempfile.mkstemp(prefix='.handoff-', dir=output_dir)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
        try:
            return validate_handoff(output_dir, Path('/mnt/user-data'), require_delivery=True)
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            raise
    finally:
        Path(temporary).unlink(missing_ok=True)

def run(model, prompt, output_dir, timeout, progress=None, transport=None, provider_label='DeepSeek', vision=None):
    key = json.loads(Path('/credentials/api.json').read_text())['api_key']
    if transport is None:
        transport = lambda path, payload, timeout: request(key, path, payload, timeout)
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content':
        'Esegui adesso l’incarico del coordinatore con run_command. '
        'Scrivi realmente i file nella cartella assegnata dal sistema. '
        'Raggruppa operazioni correlate in script o batch: non consumare un turno '
        'per ogni nota, keyframe o proprietà. Usa gli schemi salvati, senza riscoprirli. '
        'Usa submit_handoff quando la consegna minima è pronta, senza attendere il limite dei turni.'}]
    tools = [{'type': 'function', 'function': {'name': 'run_command',
        'description': 'Esegue un comando shell nella sandbox RigHaven. Salva i risultati nella cartella assegnata.',
        'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'},
            'timeout_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 1200,
                'description': 'Budget del comando, default 90s. Per render/export lunghi scegli un valore maggiore; resta entro il budget della fase.'}},
            'required': ['command']}}}]
    deadline = time.monotonic() + timeout
    usage = []
    finalization_notice = False
    for turn in range(MAX_TURNS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Timeout dello specialista ' + provider_label)
        finalizing = turn >= MAX_TURNS - 12 or remaining <= min(90, timeout / 5)
        force_handoff = turn == MAX_TURNS - 1 or remaining <= min(30, timeout / 10)
        if finalizing and not finalization_notice:
            finalization_notice = True
            messages.append({'role': 'user', 'content':
                'Concludi ora la produzione: esegui subito i batch già preparati, il salvataggio del sorgente modificabile con dipendenze e gli export essenziali. '
                'Non esplorare altri comandi e non avviare perfezionamenti. '
                'Usa submit_handoff per consegnare i prodotti reali nella cartella ' + str(output_dir) +
                '. Riporta i controlli già svolti con le loro evidenze; indica not_run per gli altri '
                'e dichiara nei warnings eventuali requisiti incompleti. '
                'I cataloghi, i batch e le prove sotto work/ non sostituiscono i prodotti richiesti.'})
        if vision is not None and not force_handoff:
            parts = vision(output_dir)
            if parts:
                messages.append({'role': 'user', 'content': [
                    {'type': 'text', 'text': 'Anteprime aggiornate del lavoro nella cartella assegnata: esamina i difetti visivi e correggili con run_command prima di proseguire.'},
                    *parts]})
        payload = {'model': model, 'messages': messages,
                   'tools': [HANDOFF_TOOL] if force_handoff else [*tools, HANDOFF_TOOL, PROGRESS_TOOL], 'max_tokens': 6000}
        if provider_label == 'DeepSeek':
            payload['thinking'] = {'type': 'disabled'}
        if force_handoff:
            payload['tool_choice'] = {'type': 'function', 'function': {'name': 'submit_handoff'}}
        if progress:
            progress.emit('finalizing' if finalizing else 'waiting_model', turn=turn + 1)
        result = transport('/chat/completions', payload, timeout=min(remaining, 180))
        if progress:
            progress.model_signal()
        usage.append(result.get('usage', {}))
        (output_dir / ('work/deepseek-usage.json' if provider_label == 'DeepSeek' else 'work/openai-usage.json')).write_text(json.dumps(usage))
        choice = result['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('Risposta ' + provider_label + ' troncata dal limite token')
        message = choice['message']
        messages.append(message)
        calls = message.get('tool_calls', [])
        if not calls:
            try:
                validate_handoff(output_dir, Path('/mnt/user-data'), require_delivery=True)
            except (OSError, ValueError) as error:
                messages.append({'role': 'user', 'content':
                    'La consegna non è ancora valida: ' + str(error).replace(key, '[REDACTED]')[:800] +
                    '. Correggi i file con run_command. La cartella obbligatoria è ' + str(output_dir) +
                    '; salva qui handoff.json secondo lo schema della skill. La risposta finale non scrive file.'})
                continue
            return message.get('content') or ''
        for call in calls:
            try:
                if call['function']['name'] == 'submit_handoff':
                    if progress:
                        progress.emit('checking')
                    handoff = submit_handoff(output_dir, json.loads(call['function']['arguments']))
                    return 'Consegna registrata e file verificati: ' + ', '.join(handoff['output_files'])
                if call['function']['name'] == 'report_progress' and not force_handoff:
                    note = json.loads(call['function']['arguments'])
                    if note.get('phase') not in ('planning', 'creating', 'exporting', 'checking', 'finalizing') or not isinstance(note.get('summary'), str):
                        raise ValueError('Aggiornamento operativo non valido')
                    if progress:
                        progress.emit(note['phase'], note['summary'])
                    messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': 'Aggiornamento registrato'})
                    continue
                if force_handoff:
                    raise ValueError('La produzione è conclusa: usa submit_handoff per i file già esistenti')
                if call['function']['name'] != 'run_command':
                    raise ValueError('Tool sconosciuto')
                arguments = json.loads(call['function']['arguments'])
                command = arguments['command']
                if not isinstance(command, str):
                    raise ValueError('command deve essere una stringa')
                command_timeout = arguments.get('timeout_seconds', 90)
                if type(command_timeout) is not int or not 1 <= command_timeout <= 1200:
                    raise ValueError('timeout_seconds deve essere un intero fra 1 e 1200')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Timeout dello specialista ' + provider_label)
                if progress:
                    try:
                        from .progress import tool_label
                    except ImportError:
                        from progress import tool_label
                    progress.emit('running_tool', tool_label(command), operation_details=getattr(progress, 'command_event', lambda *args, **kwargs: {})({'id':call['id'],'command':command}))
                completed = subprocess.run(['bash', '-lc', command], cwd=output_dir,
                    capture_output=True, text=True, errors='replace', timeout=min(command_timeout, remaining))
                if progress:
                    progress.emit('waiting_model', 'Comando concluso (uscita ' + str(completed.returncode) + ')', operation_details=getattr(progress, 'command_event', lambda *args, **kwargs: {})({'id':call['id'],'exit_code':completed.returncode,'output':completed.stderr}, completed=True))
                response = {'returncode': completed.returncode,
                            'stdout': completed.stdout[-12000:], 'stderr': completed.stderr[-3000:]}
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                if progress:
                    progress.emit('waiting_model', 'Passaggio non riuscito: il modello sta valutando la correzione')
                response = {'error': str(error).replace(key, '[REDACTED]')}
            messages.append({'role': 'tool', 'tool_call_id': call['id'],
                             'content': json.dumps(response, ensure_ascii=False)})
    raise RuntimeError('Limite dei turni ' + provider_label + ' raggiunto prima della conclusione')
