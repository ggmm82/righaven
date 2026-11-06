"""Inspectable commands and operational metadata; credentials redacted first."""
import re
import shlex


def sanitized(command):
    """Keep executable code inspectable, redact credential values before storage."""
    try:
        from .progress import SECRET
    except ImportError:
        from progress import SECRET
    if not isinstance(command, str):
        return ''
    value = command.replace('\x00', '')
    value = re.sub(r'(?i)(\b(?:authorization|cookie)\s*:\s*)[^\r\n\'\"]+', r'\1[omesso]', value)
    value = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|AIza[A-Za-z0-9_-]{25,})', '[omesso]', value)
    # Shell flags, environment assignments, JSON/Python keyword strings and
    # Authorization headers. Redact before deriving previews or fingerprints.
    names = r'(?:[\w-]*api[_-]?key|[\w-]*token|[\w-]*password|[\w-]*secret|[\w-]*(?:secret|access)[_-]?key(?:[_-]?id)?|authorization|cookie)'
    value = re.sub(r'(?i)\bBasic\s+[A-Za-z0-9+/=]{8,}', 'Basic [omesso]', value)
    value = re.sub(r'''(?ix)((?:--?)?\b''' + names + r'''["']?\s*(?:[:=]|\s)\s*)("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|[^\s;,}\n"']+)''',
                   lambda m: m[1] + (m[2][0] + '[omesso]' + m[2][0] if m[2].startswith(('"', "'")) else '[omesso]'), value)
    value = re.sub(r'(?i)([?&][\w-]*(?:key|token|secret|signature|credential|password|sig)=)[^&\s\'\"]+', r'\1[omesso]', value)
    value = re.sub(r'(?i)(https?://)[^/\s:@]+:[^/\s@]+@', r'\1[omesso]@', value)
    value = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',
                   '[chiave privata omessa]', value, flags=re.S)
    value = SECRET.sub(lambda m: m[0] if '[omesso]' in m[0] else '[omesso]', value)
    return value if len(value) <= 48000 else value[:48000] + '\n[comando troncato a 48000 caratteri]'


def describe(command):
    try:
        from .progress import APPS
    except ImportError:
        from progress import APPS
    try:
        parts = shlex.split((command or '').split('\n', 1)[0])
    except ValueError:
        parts = []
    result = {'tool': 'Shell', 'action': 'Esecuzione comando'}
    for i, part in enumerate(parts):
        name = part.rsplit('/', 1)[-1]
        if name.removesuffix('-cli') in APPS or name in ('craft', 'ffprobe', 'python', 'python3'):
            result['tool'] = name
            if name in ('python', 'python3'):
                result['action'] = 'Script Python inline'
                if i + 1 < len(parts) and re.fullmatch(r'(?:/opt/righaven-worker/|/mnt/user-data/)[\w/.-]+\.py', parts[i+1]):
                    result['action'] = parts[i+1].rsplit('/', 1)[-1]
            else:
                allowed = {'render','render-frame','export','info','inspect','verify','pack','check','run','batch','help','commands','tools','get','set','script','execute','convert','apply','filters','probe','transcode','extract_audio','mux'}
                result['action'] = next((p for p in parts[i+1:] if p in allowed), 'Esecuzione strumento')
            break
    result['files'] = list(dict.fromkeys(p for p in parts if re.fullmatch(r'/mnt/user-data/(?:outputs|uploads|workspace)/[\w/ .-]{1,240}', p)))[:8]
    safe = sanitized(command)
    if safe:
        import hashlib
        result['command_sha256'] = hashlib.sha256(safe.encode()).hexdigest()
        lines = [line for line in safe.splitlines() if line.strip()][:4]
        result['command_preview'] = '\n'.join(lines)[:480]
    return result


def diagnostic(output):
    if not isinstance(output, str):
        return ''
    # Error categories provide useful context without copying data printed by
    # a command (which may be a document, credential file or model prompt).
    for pattern, label in [
        (r'FileNotFoundError|No such file|not found', 'File, dipendenza o comando non trovato'),
        (r'PermissionError|Permission denied', 'Accesso al file non consentito'),
        (r'unrecognized arguments|unknown option|unexpected argument', 'Parametro CLI non riconosciuto'),
        (r'JSONDecodeError|invalid json', 'Documento JSON non valido'),
        (r'TimeoutError|timed out', 'Tempo di esecuzione esaurito'),
        (r'AssertionError', 'Verifica dichiarata dal comando non superata'),
        (r'TypeError|ValueError', 'Tipo o valore non accettato dallo strumento')]:
        if re.search(pattern, output[-16000:], re.I):
            return label
    return ''


def public(value):
    try:
        from .progress import clean_summary
    except ImportError:
        from progress import clean_summary
    if not isinstance(value, dict):
        return {}
    result = {k: clean_summary(value[k], 180) for k in ('tool','action','diagnostic','started_at','finished_at','id') if isinstance(value.get(k), str)}
    for k in ('duration_seconds','exit_code'):
        import math
        if type(value.get(k)) in (int,float) and math.isfinite(value[k]):
            result[k] = value[k]
    if isinstance(value.get('record_path'), str) and re.fullmatch(r'/mnt/user-data/outputs/[\w/.-]+/work/commands/[a-f0-9]{24}/status\.json', value['record_path']):
        result['record_path'] = value['record_path']
    if isinstance(value.get('command_path'), str) and re.fullmatch(r'/mnt/user-data/outputs/[\w/.-]+/work/commands/[a-f0-9]{24}/command\.txt', value['command_path']):
        result['command_path'] = value['command_path']
    if isinstance(value.get('command_preview'), str):
        result['command_preview'] = sanitized(value['command_preview'])[:480]
    if isinstance(value.get('command_sha256'), str) and re.fullmatch('[a-f0-9]{64}', value['command_sha256']):
        result['command_sha256'] = value['command_sha256']
    result['files'] = [clean_summary(p, 280) for p in (value.get('files') if isinstance(value.get('files'), list) else [])[:4] if isinstance(p, str) and p.startswith('/mnt/user-data/')]
    result['changed_files'] = [clean_summary(p, 180) for p in (value.get('changed_files') if isinstance(value.get('changed_files'), list) else [])[:4] if isinstance(p, str)]
    return result
