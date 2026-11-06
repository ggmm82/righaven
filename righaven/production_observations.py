"""Preserve unsuccessful experiments without approving claims as learned skills."""
import json
from pathlib import Path

from .acceptance import fingerprint
from .progress import utcnow
from .project_skills import redact_memory
from .source_packages import digest


def observations(workspace, attempt, role, source_thread):
    from .projects import artifact_path, workspace_path
    from .experience import method_record
    if attempt.get('status') == 'running':
        return []
    directory = workspace_path(workspace, attempt.get('output_dir', ''))
    if not directory:
        return []
    report = artifact_path(workspace, directory / 'handoff.json')
    if not report or report.stat().st_size > 100000:
        return []
    try:
        value = json.loads(report.read_text())
        checks = value.get('checks', [])
        if not isinstance(checks, list):
            return []
        from .handoff import blocking_checks
        checks = [check for check in blocking_checks([c for c in checks if isinstance(c, dict)])
                  if isinstance(check.get('name'), str) and isinstance(check.get('evidence'), str)
                  and check['evidence'].strip()][:3]
        if not checks:
            return []
        files, seen, remaining = [], set(), 16 * 1024 * 1024
        outputs, previews = value.get('output_files', []), value.get('previews', [])
        if not isinstance(outputs, list) or not isinstance(previews, list):
            return []
        # Keep collection cheap on the gateway: previews before large renders,
        # bounded evidence, never rehash entire video/source archives on each poll.
        for name in [*previews, *outputs][:48]:
            path = artifact_path(workspace, name) if isinstance(name, str) else None
            if (path and path.is_relative_to(directory) and path != report and path not in seen
                    and path.stat().st_size <= remaining):
                seen.add(path)
                remaining -= path.stat().st_size
                files.append({'path': '/mnt/user-data/' + path.relative_to(Path(workspace).resolve()).as_posix(),
                              'sha256': digest(path)})
                if len(files) == 3:
                    break
        if not files:
            return []
        records, report_hash = [], digest(report)
        for check in checks:
            observation = redact_memory({
                'kind': 'production_observation', 'source_thread': source_thread,
                'criterion': check['name'][:1000], 'status': 'reported_failure',
                'method': 'producer_report', 'evidence': check['evidence'][:1500],
                'corrections': [], 'tools': role.get('tool_versions', {}), 'scope_known': bool(role),
                'producer_method': method_record(workspace, attempt),
                'source_report': '/mnt/user-data/' + report.relative_to(Path(workspace).resolve()).as_posix(),
                'report_sha256': report_hash, 'evidence_files': files,
                'impact': {'level': 'unknown', 'basis': 'hypothesis',
                           'reason': 'Difetto dichiarato; causa, portata e beneficio della correzione da verificare.'},
                'limitations': ['Osservazione del produttore, non revisione indipendente. Non attiva una skill né prova una soluzione.',
                                'Evidenze limitate a tre file piccoli; non è una verifica completa del prodotto.'],
            })
            observation['origin_id'] = fingerprint(observation)
            records.append({'id': fingerprint(observation), 'at': attempt.get('finished_at') or utcnow(),
                            'observation': observation})
        return records
    except (OSError, ValueError, TypeError, AttributeError):
        return []


def recent_context(workspace, project):
    """Carry observed defects across role changes, not only formal review reports."""
    from .project_brief import orientation
    active = set(orientation(project)['active_step_ids'])
    contract = (project.get('acceptance') or {}).get('hash')
    attempts = sorted((a for s in project.get('steps', []) if s['id'] in active for a in s.get('attempts', [])
                       if a.get('status') != 'running' and (not a.get('context',{}).get('contract')
                           or a['context']['contract'] == contract)), key=lambda a: a.get('finished_at', ''), reverse=True)
    result, directories = [], set()
    for attempt in attempts:
        directory = attempt.get('output_dir')
        if not directory or directory in directories:
            continue
        directories.add(directory)
        if len(directories) > 3:
            break
        for record in observations(workspace, attempt, {}, None):
            value = record['observation']
            result.append({'criterion': value['criterion'][:200], 'evidence': value['evidence'][:600],
                           'report': value['source_report'], 'report_sha256': value['report_sha256'],
                           'files': [f['path'] for f in value['evidence_files'][:3]],
                           'status': 'reported_failure'})
            if len(result) == 3:
                return result
    return result
