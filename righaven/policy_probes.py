"""Executable checks a Policy Book sheet can require on the finished product.

A final check may name a probe from this closed catalog instead of relying
only on a reviewer's judgement. The probe runs the named program on the exact
product file, in a container prepared with that catalog tool, with no network,
no capabilities, a read-only root and the file mounted read-only. Results are
stored with the product SHA-256, so a new version is probed again.
"""
import json
from pathlib import Path
import subprocess
import uuid

from .progress import clean_summary, utcnow

PDF = ('.pdf',)
MEDIA = ('.mp4', '.mov', '.webm', '.mkv', '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac')
# id -> catalog tool, accepted file types, command (FILE is the mounted product), title.
PROBES = {
    'pdf_structure': {'tool': 'qpdf', 'suffixes': PDF, 'argv': ['qpdf', '--check', 'FILE'],
                      'title': ('Struttura PDF valida (qpdf --check)', 'Valid PDF structure (qpdf --check)')},
    'pdf_text': {'tool': 'poppler', 'suffixes': PDF, 'argv': ['pdftotext', '-q', 'FILE', '-'],
                 'title': ('Testo estraibile dal PDF (pdftotext)', 'Text extractable from the PDF (pdftotext)')},
    'pdfa_conformance': {'tool': 'verapdf', 'suffixes': PDF, 'argv': ['verapdf', '--format', 'text', 'FILE'],
                         'title': ('Conformità PDF/A (veraPDF)', 'PDF/A conformance (veraPDF)')},
    'media_streams': {'tool': 'ffmpeg', 'suffixes': MEDIA,
                      'argv': ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name', '-of', 'json', 'FILE'],
                      'title': ('Flussi audio/video leggibili (ffprobe)', 'Readable audio/video streams (ffprobe)')},
    'no_secrets': {'tool': 'gitleaks', 'suffixes': None,
                   'argv': ['gitleaks', 'dir', '--no-banner', '--redact', '--exit-code', '1', 'FILE'],
                   'title': ('Nessun segreto nel prodotto (gitleaks)', 'No secrets in the product (gitleaks)')},
}
TIMEOUT = 300


def catalog():
    return [{'id': key, 'tool': value['tool'], 'suffixes': list(value['suffixes'] or []),
             'title': {'it': value['title'][0], 'en': value['title'][1]}} for key, value in PROBES.items()]


def verdict(probe, returncode, stdout, stderr):
    """(passed, evidence) from the program's exit status and output."""
    output = (stdout or '').strip()
    if probe == 'pdf_text':
        words = len(output.split())
        return returncode == 0 and words > 0, f'{words} parole estratte' if returncode == 0 else 'pdftotext: ' + (stderr or '')[:200]
    if probe == 'pdfa_conformance':
        passed = returncode == 0 and output.startswith('PASS')
        return passed, (output.splitlines() or [stderr or ''])[0][:240]
    if probe == 'media_streams':
        try:
            streams = json.loads(output or '{}').get('streams', [])
        except ValueError:
            streams = []
        kinds = sorted({s.get('codec_type') + ':' + str(s.get('codec_name')) for s in streams if s.get('codec_type') in ('audio', 'video')})
        return returncode == 0 and bool(kinds), ', '.join(kinds) or 'nessun flusso audio/video leggibile' + (': ' + stderr[:160] if stderr else '')
    if probe == 'no_secrets':
        return returncode == 0, 'nessun segreto rilevato' if returncode == 0 else 'segreti rilevati (valori oscurati): ' + (stdout or stderr or '')[:200]
    return returncode == 0, (output or stderr or 'exit ' + str(returncode))[:240]


def applicable(probe, path):
    suffixes = PROBES[probe]['suffixes']
    return suffixes is None or Path(path).suffix.lower() in suffixes


def run(probe, path, *, image=None):
    """Run one probe on the exact file; returns {status, evidence, tool, at}."""
    spec = PROBES[probe]
    path = Path(path)
    if not applicable(probe, path):
        return {'status': 'failed', 'tool': spec['tool'], 'at': utcnow(),
                'evidence': f'Il controllo {probe} riguarda file ' + ', '.join(spec['suffixes']) + f', non {path.suffix or "senza estensione"}'}
    from .docker_runtime import docker, mount
    target = '/probe/' + ('product' + path.suffix.lower())
    argv = [target if item == 'FILE' else item for item in spec['argv']]
    name = 'rh-probe-' + uuid.uuid4().hex[:12]
    claim = None
    if image is None:
        from .environment_runtime import ensure
        claim = name
        prepared = ensure([spec['tool']], claim=claim)
        image = prepared.get('image_id') or prepared.get('image')
    try:
        completed = subprocess.run(['docker', 'run', '--rm', '--name', name, '--pull=never', '--network=none', '--cap-drop=ALL',
                                    '--security-opt=no-new-privileges', '--read-only', '--tmpfs', '/tmp:rw,size=256m',
                                    '--pids-limit=128', '--memory=1536m', '--cpus=1', '--env', 'HOME=/tmp',
                                    '--mount', mount(path, target, True), '--entrypoint', argv[0], image, *argv[1:]],
                                   capture_output=True, text=True, timeout=TIMEOUT)
        passed, evidence = verdict(probe, completed.returncode, completed.stdout, completed.stderr)
    except subprocess.TimeoutExpired:
        try:
            docker('rm', '-f', name)
        except (OSError, subprocess.SubprocessError):
            pass
        passed, evidence = False, f'Tempo limite di {TIMEOUT} s superato'
    finally:
        if claim:
            from .environment_runtime import release_claim
            release_claim(claim)
    return {'status': 'passed' if passed else 'failed', 'evidence': clean_summary(evidence, 300), 'tool': spec['tool'], 'at': utcnow()}


def checks(sheet):
    return [c for c in sheet['final_checks'] if c.get('probe')] if sheet['final_checks'] != 'acceptance' else []
