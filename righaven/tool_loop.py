"""Bounded tool loop of workers that use an OpenAI-compatible Chat Completions API.

Codex, Claude Code and Antigravity bring their own agent; this loop gives any model with
function calling the same contract: shell commands in the sandbox, progress notes and a
checked handoff.
"""
import json
import os
import tempfile
from pathlib import Path
import subprocess
import time

MAX_TURNS = 64
# A reply cut by the token limit is not fatal: the model is asked to continue in smaller steps.
MAX_TRUNCATIONS = 3
# Older command outputs are shortened when the conversation grows, so long jobs do not exceed
# the model context (about 30k tokens of history kept in full).
HISTORY_CHARS = 120_000
KEEP_RECENT = 8
SHORT_OUTPUT = 1200

try:
    from .handoff import HANDOFF_SCHEMA, validate_handoff
except ImportError:
    from handoff import HANDOFF_SCHEMA, validate_handoff


def compact(messages):
    """Shorten tool outputs older than the last few turns once the history is large."""
    size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    if size <= HISTORY_CHARS:
        return False
    changed = False
    for message in messages[2:-KEEP_RECENT]:
        content = message.get('content')
        if message.get('role') == 'tool' and isinstance(content, str) and len(content) > SHORT_OUTPUT:
            message['content'] = content[:SHORT_OUTPUT // 2] + ' …[output shortened: rerun the command if needed]… ' + content[-SHORT_OUTPUT // 2:]
            changed = True
        elif message.get('role') == 'user' and isinstance(content, list):
            # Earlier preview images are replaced by a note; the latest previews stay.
            message['content'] = [part for part in content if part.get('type') == 'text'] or 'Anteprime precedenti omesse.'
            changed = True
    return changed


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

def run(model, prompt, output_dir, timeout, progress=None, transport=None, provider_label='Provider OpenAI compatibile', vision=None):
    key = json.loads(Path('/credentials/api.json').read_text())['api_key']
    if transport is None:
        raise ValueError('Transport del provider mancante')
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
    truncations = 0
    for turn in range(MAX_TURNS):
        compact(messages)
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
        if force_handoff:
            payload['tool_choice'] = {'type': 'function', 'function': {'name': 'submit_handoff'}}
        if progress:
            progress.emit('finalizing' if finalizing else 'waiting_model', turn=turn + 1)
        result = transport('/chat/completions', payload, timeout=min(remaining, 180))
        if progress:
            progress.model_signal()
        usage.append(result.get('usage', {}))
        if progress and hasattr(progress, 'tokens'):
            progress.tokens(result.get('usage'))
        (output_dir / 'work/openai-usage.json').write_text(json.dumps(usage))
        choice = result['choices'][0]
        message = choice['message']
        if choice.get('finish_reason') == 'length':
            # A cut reply may hold an incomplete tool call: drop it and ask for smaller steps.
            truncations += 1
            if truncations > MAX_TRUNCATIONS:
                raise RuntimeError('Risposta ' + provider_label + ' troncata dal limite token più volte')
            messages.append({'role': 'user', 'content':
                'La risposta precedente è stata interrotta dal limite di token e non è stata eseguita. '
                'Procedi a passi più piccoli: scrivi i file lunghi in più comandi (per esempio con cat >> a blocchi) '
                'e non ripetere contenuti già salvati.'})
            continue
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
