"""Capture selected tool-use findings from workers, never their whole transcript."""
import json
from pathlib import Path
import math
import re

from .acceptance import fingerprint
from .lessons import validate, validate_impact
from .progress import utcnow, workspace_key
from .project_skills import redact_memory, read_document
from .source_packages import digest


def technical_validation(workspace, directory, candidate, artifact):
    """Check bounded JSON assertions against a completed supervised operation.

    This proves a recorded technical test, never visual quality or a production
    method. All inputs must be fresh files in this job, not another user's job.
    """
    check = candidate.get('validation')
    if not isinstance(check, dict):
        return {'status': 'not_run', 'reason': 'Manca una prova tecnica verificabile automaticamente.'}
    try:
        operation = artifact(workspace, check['operation_path'])
        result = artifact(workspace, check['result_path'])
        if (not operation or operation.name != 'status.json'
                or operation.parent.parent not in (directory / 'work/operations', directory / 'work/commands')
                or not re.fullmatch(r'[a-f0-9]{24}', operation.parent.name)
                or operation.stat().st_size > 16000 or not result
                or not result.is_relative_to(directory) or result == operation
                or result.name == 'tool-lessons.json' or result.stat().st_size > 1048576):
            raise ValueError('Prova fuori dall’incarico o non valida')
        status = json.loads(operation.read_text())
        if status.get('state') != 'completed' or status.get('returncode') != 0 or status.get('oom_kills'):
            raise ValueError('Operazione non conclusa correttamente')
        data = json.loads(result.read_text())
        assertions = check['assertions']
        if not isinstance(assertions, list) or not 1 <= len(assertions) <= 8:
            raise ValueError('Servono da una a otto verifiche puntuali')
        for assertion in assertions:
            pointer = assertion['pointer']
            if not isinstance(pointer, str) or not pointer.startswith('/') or len(pointer) > 300:
                raise ValueError('Percorso JSON non valido')
            actual = data
            for part in pointer[1:].split('/'):
                part = part.replace('~1', '/').replace('~0', '~')
                actual = actual[int(part)] if isinstance(actual, list) else actual[part]
            expected = assertion['equals']
            if type(actual) is not type(expected) or actual != expected:
                raise ValueError('Asserzione tecnica fallita')
        return {'status': 'passed', 'operation_sha256': digest(operation), 'result_sha256': digest(result),
                'assertions': assertions, 'notice': 'Test tecnico registrato dalla sandbox; non è una valutazione estetica né una riproduzione indipendente.'}
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return {'status': 'not_run', 'reason': 'Prova tecnica assente, non valida o non superata.'}


def measurement(workspace, directory, candidate, artifact):
    value = candidate.get('measurement') or {}
    result = {}
    for stage in ('before', 'after'):
        path = artifact(workspace, value.get(stage, ''))
        if (not path or path.name != 'status.json' or path.parent.parent != directory / 'work/operations'
                or not re.fullmatch(r'[a-f0-9]{24}', path.parent.name) or path.stat().st_size > 16000):
            raise ValueError('La misura richiede due stati reali del supervisore')
        status = json.loads(path.read_text())
        seconds = status.get('elapsed_seconds')
        if (status.get('state') != 'completed' or status.get('returncode') != 0
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0):
            raise ValueError('Confronto temporale non disponibile per questa operazione')
        result[stage] = {'seconds': seconds, 'path': '/mnt/user-data/' + path.relative_to(Path(workspace).resolve()).as_posix(), 'sha256': digest(path)}
    if result['before']['path'] == result['after']['path']:
        raise ValueError('La prova prima e dopo non può coincidere')
    result['notice'] = 'Tempi registrati dal supervisore; confrontabilità degli input e qualità restano da verificare.'
    return result


def observations(workspace, attempt, role, source_thread, captured=()):
    from .projects import artifact_path, workspace_path
    if attempt.get('status') == 'running':
        return []
    directory = workspace_path(workspace, attempt.get('output_dir', ''))
    if not directory:
        return []
    manifest = artifact_path(workspace, directory / 'work/tool-lessons.json')
    if not manifest or manifest.stat().st_size > 24000:
        return []
    manifest_hash = digest(manifest)
    capture_key = fingerprint({'workspace': workspace_key(workspace), 'job': directory.name, 'manifest': manifest_hash})
    if capture_key in captured:
        return []
    try:
        value = json.loads(manifest.read_text())
        candidates = value if isinstance(value, list) else value['lessons']
        if not isinstance(candidates, list) or len(candidates) > 3:
            return []
    except (OSError, ValueError, KeyError, TypeError):
        return []
    installed = role.get('tool_versions', {})
    if attempt.get('tool_environment'):
        try:
            installed = json.loads(read_document(workspace, attempt['tool_environment']))
        except (OSError, ValueError, TypeError):
            return []
    records = []
    for candidate in candidates:
        try:
            lesson = validate(candidate['lesson'])
            if any(t not in installed for t in lesson['tools']):
                continue
            evidence = candidate['evidence']
            if not isinstance(evidence, str) or not 5 <= len(evidence.strip()) <= 1500:
                continue
            filenames = candidate['evidence_paths']
            if not isinstance(filenames, list) or not 1 <= len(filenames) <= 6:
                continue
            proofs = []
            for name in filenames:
                if not isinstance(name, str):
                    raise ValueError('Riferimento non valido')
                path = artifact_path(workspace, name)
                if not path or not path.is_relative_to(directory) or path == manifest:
                    raise ValueError('La prova deve appartenere alla sandbox, non essere il manifesto stesso')
                proofs.append({'path': name, 'sha256': digest(path)})
            impact = validate_impact(candidate.get('impact'))
            measured = None
            if impact['basis'] == 'measured':
                measured = measurement(workspace, directory, candidate, artifact_path)
            # This records a worker finding with real files, not independent replay.
            observation = redact_memory({
                'kind': 'sandbox_tool_use', 'capture_key': capture_key, 'source_thread': source_thread,
                'criterion': lesson['title'], 'status': 'sandbox_observation', 'method': 'worker_report',
                'evidence': evidence.strip(), 'corrections': [], 'suggested_lesson': lesson,
                'impact': impact, 'measurement': measured,
                'technical_validation': technical_validation(workspace, directory, candidate, artifact_path),
                'tools': {t: installed.get(t, 'unknown') for t in lesson['tools']},
                'evidence_files': proofs, 'source_report': str(manifest), 'report_sha256': manifest_hash,
                'product_sha256': fingerprint(proofs), 'scope_known': bool(installed),
                'limitations': ['Osservazione dichiarata dalla sandbox con file e versioni registrati; non è una riproduzione indipendente né una verifica della qualità del prodotto.'],
            })
            observation['origin_id'] = fingerprint(observation)
            records.append({'id': fingerprint(observation), 'at': attempt.get('finished_at') or utcnow(), 'observation': observation})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            from .learning_notes import preserve_note
            record = preserve_note(workspace, attempt, manifest, manifest_hash, capture_key,
                                   candidate, installed, source_thread, error)
            if record:
                records.append(record)
    return records
