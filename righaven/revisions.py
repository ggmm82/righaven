"""Read-only version labels and review targets, independent of specialist titles."""
from pathlib import Path
from .handoff import product_files
from functools import lru_cache


@lru_cache(maxsize=128)
def _file_hash(path, signature):
    from .source_packages import digest
    value = digest(path)
    if _signature(path) != signature:
        raise ValueError('File modificato durante la verifica')
    return value


def _signature(path):
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def unchanged(workspace, filename, expected, artifact):
    """Reuse byte checks only while filesystem identity and timestamps match."""
    path = artifact(workspace, filename)
    try:
        return bool(expected and path and path.is_file() and _file_hash(path, _signature(path)) == expected)
    except (OSError, ValueError):
        return False


def number_attempts(project):
    """Persist monotonically increasing numbers, including failed/in-progress work."""
    attempts = [a for step in project['steps'] for a in step['attempts']
                if (a.get('context') or {}).get('purpose') == 'delivery'
                or (a.get('context') or {}).get('purpose', 'work') not in ('preview', 'review')
                and project.get('product_path') and project['product_path'] in a.get('output_files', [])]
    attempts.sort(key=lambda a: (a.get('started_at', ''), a.get('finished_at', '')))
    counter = max([project.get('version_counter', 0), *[a.get('version_number', 0) for a in attempts]])
    changed = False
    for attempt in attempts:
        if not attempt.get('version_number'):
            counter += 1
            attempt['version_number'] = counter
            changed = True
    if changed:
        project['version_counter'] = counter
    return changed


def annotate(deliveries, project, workspace, artifact):
    attempts = [(step, attempt) for step in project['steps'] for attempt in step['attempts']]
    attempts.sort(key=lambda item: (item[1].get('started_at', ''), item[1].get('finished_at', ''), item[0]['id']))
    by_id = {d['id']: d for d in deliveries}
    targets = {}
    previous_product = None
    for step, attempt in attempts:
        identifier = (attempt.get('delivery_record') or {}).get('id') or Path(attempt.get('output_dir', '')).name or step['id']
        purpose = (attempt.get('context') or {}).get('purpose', 'work')
        current = bool(project.get('product_path') and project['product_path'] in attempt.get('output_files', []))
        category = ('review' if purpose == 'review' or attempt.get('quality_review') else 'sample' if purpose == 'preview'
                    else 'version' if purpose == 'delivery' or current else 'contribution')
        delivery = by_id.get(identifier)
        if delivery is None:
            continue
        delivery.update(category=category, version=attempt.get('version_number') if category == 'version' else None,
                        execution_status=attempt.get('status', ''), file_count=len(attempt.get('output_files', [])),
                        role_title=attempt.get('role_title', ''))
        if category == 'version':
            validated = attempt.get('validated', attempt.get('status') == 'completed')
            delivery['version_state'] = ('working' if attempt.get('status') == 'running' else
                'partial' if not validated else 'needs_revision' if
                (attempt.get('delivery_record') or {}).get('technical_status') != 'passed' else 'candidate')
            if attempt.get('recovery'):
                delivery['recovery'] = attempt['recovery']
            files = (attempt.get('delivery_record') or {}).get('files', [])
            exports = tuple(sorted(f['sha256'] for f in product_files(files) if f.get('sha256')))
            sources = {f['sha256'] for f in files if f.get('role') in ('editable_source','source_archive') and f.get('sha256')}
            delivery['content_version'] = delivery.get('version')
            if exports and previous_product and exports == previous_product[0]:
                previous, old_sources = previous_product[1:]
                delivery.update(unchanged_content=True, change_kind='sources' if sources != old_sources else 'metadata',
                    content_version=previous.get('content_version'), based_on_delivery_id=previous['id'])
            if exports:
                previous_product = (exports, delivery, sources)
        for filename in attempt.get('output_files', []):
            path = artifact(workspace, filename)
            if path:
                targets[str(path)] = delivery
    for step, attempt in attempts:
        review = attempt.get('quality_review')
        if not review:
            continue
        identifier = (attempt.get('delivery_record') or {}).get('id') or Path(attempt.get('output_dir', '')).name or step['id']
        delivery = by_id.get(identifier)
        if not delivery:
            continue
        target = artifact(workspace, review.get('product_path', ''))
        parent = targets.get(str(target)) if target else None
        delivery['review'] = {'target_delivery_id': parent['id'] if parent else None,
            'target_version': parent.get('version') if parent else None,
            'target_label': parent['title'] if parent else 'Risultato precedente non presente nell’elenco',
            'status': review.get('status', 'needs_review'), 'validated': bool(attempt.get('validated')),
            'matches_current_brief': not project.get('acceptance') or review.get('contract_hash') == project['acceptance']['hash'],
            'report_path': review.get('report_path', ''), 'correction_count': len(review.get('revision_actions', []))}
    if workspace is not None:
        from .projects import review_matches
        accepted = project.get('user_acceptance') or {}
        reviews = [a for _, a in attempts if a.get('validated') and a.get('quality_review')]
        reviews.sort(key=lambda a: a.get('finished_at', ''), reverse=True)
        for delivery in deliveries:
            if delivery.get('version_state') != 'candidate':
                continue
            attempt = next((a for _, a in attempts if
                ((a.get('delivery_record') or {}).get('id') or Path(a.get('output_dir', '')).name) == delivery['id']), {})
            exports = product_files((attempt.get('delivery_record') or {}).get('files', []))
            for export in exports:
                path = artifact(workspace, export.get('path', ''))
                if not path or not unchanged(workspace, export.get('path', ''), export.get('sha256'), artifact):
                    continue
                if (accepted.get('status') == 'passed' and accepted.get('sha256') == export['sha256']
                        and artifact(workspace, accepted.get('product_path', '')) == path
                        and accepted.get('contract_hash', (project.get('acceptance') or {}).get('hash')) == (project.get('acceptance') or {}).get('hash')):
                    if all(unchanged(workspace, f.get('path', ''), f.get('sha256'), artifact)
                           for f in (attempt.get('delivery_record') or {}).get('files', [])):
                        delivery['version_state'] = 'approved'
                    break
                review = next((a['quality_review'] for a in reviews if
                    a['quality_review'].get('contract_hash') == (project.get('acceptance') or {}).get('hash')
                    and a['quality_review'].get('sha256') == export['sha256']
                    and (not a['quality_review'].get('report_sha256') or unchanged(workspace,
                         a['quality_review'].get('report_path', ''), a['quality_review']['report_sha256'], artifact))
                    and all(unchanged(workspace, p, h, artifact) for p, h in a['quality_review'].get('input_hashes', {}).items())
                    and (artifact(workspace, a['quality_review'].get('product_path', '')) == path
                         or review_matches(project, a['quality_review'], export['path'], workspace))), None)
                if review:
                    delivery['version_state'] = 'approved' if review['status'] == 'passed' else 'needs_revision' if review['status'] == 'needs_revision' else 'candidate'
                    break
    return deliveries
