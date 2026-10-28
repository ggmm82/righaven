"""Small, shared descriptions of recoverable work and provider failures."""
import json
from pathlib import Path
import re
import subprocess


def failure_info(error):
    text = str(error).lower()
    legacy_guidance = text.startswith(('antigravity: incarico non completato; verifica modello, login e quota',
                                      'antigravity: richiesta fallita; verifica login, modello e quota'))
    if any(s in text for s in ('memoria esaurita', 'out of memory', 'oom_kill')):
        return {'code': 'resource_memory', 'retryable': False,
                'message': 'Il worker ha esaurito la memoria; i file salvati restano disponibili.',
                'action': 'Controlla il budget condiviso in La tua squadra e riprendi dal checkpoint; non ripetere lo stesso render con gli stessi limiti.'}
    if not legacy_guidance and any(s in text for s in ('quota', 'usage limit', 'resource_exhausted', 'out of credit', 'billing', 'insufficient_balance')):
        return {'code': 'provider_quota', 'retryable': False,
                'message': 'Il servizio AI ha esaurito la quota: i file già salvati sono conservati.',
                'action': 'Apri La tua squadra e scegli un servizio disponibile, oppure attendi il ripristino della quota.'}
    if any(s in text for s in ('unauthorized', '401', 'chiave', 'credenzial', 'login required', 'authentication')):
        return {'code': 'provider_auth', 'retryable': False,
                'message': 'Il collegamento al servizio AI richiede un controllo.',
                'action': 'Apri La tua squadra e verifica il collegamento del servizio.'}
    if 'interruzione della fase richiesta' in text:
        return {'code':'work_cancelled','retryable':False,
                'message':'Fase interrotta su richiesta; i risultati precedenti sono conservati.',
                'action':'Ispeziona i file salvati e ripianifica il seguito; non rilanciare automaticamente la stessa fase.'}
    if 'budget di attesa del modello' in text:
        return {'code': 'provider_wait_limit', 'retryable': True,
                'message': 'Il modello non ha inviato nuovi eventi entro il budget di attesa.',
                'action': 'Conserva e ispeziona i file prodotti; valuta una continuazione mirata o un altro modello. Non ricominciare tutto.'}
    if 'budget di avvio codex' in text:
        return {'code': 'provider_startup_limit', 'retryable': True,
                'message': 'Codex non ha confermato l’avvio dell’incarico entro un minuto.',
                'action': 'Verifica il collegamento e riusa i file salvati. Questa è un’attesa di avvio, non una generazione immagini conclusa né una pulizia del container.'}
    if any(s in text for s in ('turni', 'turn limit', 'timeout', 'timed out', 'tempo massimo', 'limite della singola', 'tempo esaurito')):
        return {'code': 'work_limit', 'retryable': True,
                'message': 'Questo incarico si è fermato; puoi riusare i file prodotti.',
                'action': 'Ispeziona i risultati disponibili e assegna solo il recupero, la verifica o l’integrazione mancanti.'}
    return {'code': 'work_error', 'retryable': True,
            'message': 'Un passaggio non è riuscito; il resto del lavoro resta disponibile.',
            'action': 'Usa il dettaglio dell’errore per una correzione mirata o una strada alternativa.'}


def partial_files(output_dir):
    """Inventory is not a successful handoff or a claim of editability."""
    root = Path(output_dir)
    files = []
    if not root.is_dir() or root.is_symlink():
        return files
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if (any(p.startswith('.') or p in ('work', 'assets', 'Audio Files') for p in relative.parts)
                or path.name == 'handoff.json' or path.is_symlink()):
            continue
        if path.resolve().is_relative_to(root.resolve()) and path.is_file() and path.stat().st_size:
            files.append(str(path))
        if len(files) >= 30:
            break
    return files


def validate_media(path, requirements):
    """Independent final-file checks, executed only inside the native worker."""
    if not requirements:
        return []
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=30, check=True)
    info = json.loads(result.stdout)
    kinds = {s.get('codec_type') for s in info.get('streams', [])}
    checks = []
    for kind in ('video', 'audio'):
        if requirements.get(kind):
            checks.append({'name': 'Prodotto finale: traccia ' + kind,
                           'status': 'passed' if kind in kinds else 'failed',
                           'evidence': 'Flussi reali rilevati: ' + ', '.join(sorted(kinds))})
    if requirements.get('audio') and 'audio' in kinds:
        audio = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(path), '-vn', '-af', 'volumedetect',
                                '-f', 'null', '-'], capture_output=True, text=True, timeout=45, check=True)
        measured = re.search(r'mean_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB', audio.stderr)
        # volumedetect represents digital silence as about -91 dB after its
        # internal 16-bit conversion; checking only "-inf" accepts silent AAC.
        level = float(measured.group(1)) if measured else float('-inf')
        non_silent = level > -75
        checks.append({'name': 'Prodotto finale: audio non silenzioso',
                       'status': 'passed' if non_silent else 'failed',
                       'evidence': f'Livello medio {level} dBFS, soglia operativa -75 dBFS; '
                                   'non equivale ad ascolto o valutazione musicale.'})
    return checks
