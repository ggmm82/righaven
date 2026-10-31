"""Delivery gate: whether a product is the verified, reviewed output of this project."""

from .progress import clean_summary
from .source_packages import digest
from .project_store import artifact_path


def media_accepted(record, value):
    if record.get('finalization_pending'):
        return False
    required = {k for k, v in value.get('requirements', {}).items() if v}
    return not required or (value.get('product_path') in record.get('verified_products', [])
        and all(record.get('requirements', {}).get(k) is True for k in required))


def delivery_integrity(workspace, value, target):
    """Technical gate shared by completion and final validation; returns the issue or None."""
    if not target:
        return 'Indica il prodotto finale verificato, non un elenco di file intermedi'
    target_hash = digest(target)
    deliveries = [a.get('delivery_record') or {} for s in value['steps'] for a in s['attempts']
                  if any(artifact_path(workspace, p) == target for p in a.get('output_files', []))]
    if not any(d.get('technical_status') == 'passed' and media_accepted(d, value) and all(
            artifact_path(workspace, f.get('path', '')) and digest(artifact_path(workspace, f['path'])) == f.get('sha256')
            for f in d.get('files', [])) and any(
            artifact_path(workspace, f.get('path', '')) == target and f.get('sha256') == target_hash
            for f in d.get('files', [])) for d in deliveries):
        return 'Consegna non collaudata o sorgenti incompleti: usa purpose=delivery e correggi delivery.issues. I file restano disponibili come bozza.'
    return None


def standard_reviews(value):
    """Reviews against the acceptance contract; policy-sheet reviews are tracked separately."""
    return sorted((a for s in value['steps'] for a in s['attempts'] if a.get('quality_review') and not a.get('policy_review')),
                  key=lambda a: a.get('finished_at', ''), reverse=True)


def standard_review(workspace, value, target_hash):
    """The latest separate review still valid for this product and request, if any."""
    review = next((a['quality_review'] for a in standard_reviews(value)
                   if review_matches(value, a['quality_review'], value.get('product_path'), workspace)), None)
    if (not review or review.get('sha256') != target_hash
            or (value.get('acceptance') and review.get('contract_hash') != value['acceptance']['hash'])
            or not all(artifact_path(workspace, p) and digest(artifact_path(workspace, p)) == sha
                       for p, sha in review.get('reference_hashes', {}).items())):
        return None
    if not value.get('acceptance') and value.get('requirements', {}).get('audio') and not any(
            c.get('method') == 'listening' and c.get('status') == 'passed' for c in review.get('criteria', [])):
        return {**review, 'status': 'needs_review'}
    return review


def delivery_summary(record):
    if not record:
        return None
    return {**{k: record.get(k) for k in ('id', 'title', 'purpose', 'technical_status', 'requirements', 'verified_products', 'source_status')},
        **{k:record[k] for k in ('environment_checks','source_coverage','timing','finalization_pending','source_package_status','reused_archive_checks','early_delivery','quality_status') if record.get(k)},
        'historical_checks': [{k:clean_summary(c.get(k, '')) for k in ('name','status','evidence','scope','superseded_by')}
                              for c in record.get('historical_checks', [])[:8]],
        'issues': [clean_summary(s) for s in record.get('issues', [])[:8]],
        'files': [{**{k: f.get(k) for k in ('path', 'sha256', 'role', 'primary')},
                   **{k: clean_summary(f.get(k, '')) for k in ('open_with', 'editability')},
                   'limitations': [clean_summary(s) for s in f.get('limitations', [])[:3]]}
                  for f in record.get('files', [])[:40]]}


def visible_attempts(step, product_path):
    """A review is another attempt, not a replacement for the product it checks."""
    attempts = step['attempts']
    visible = list(reversed(attempts[-5:]))
    selected = next((a for a in reversed(attempts) if product_path and product_path in a.get('output_files', [])), None)
    if selected is not None and selected not in visible:
        visible.append(selected)
    return visible


def review_matches(value, review, target_path, workspace):
    target = artifact_path(workspace, target_path)
    original = artifact_path(workspace, review.get('product_path', ''))
    if not target:
        return False
    if original == target:
        return not review.get('sha256') or digest(target) == review['sha256']
    if not review.get('input_hashes') or digest(target) != review.get('sha256'):
        return False
    if review.get('report_sha256'):
        report = artifact_path(workspace, review.get('report_path',''))
        if not report or digest(report) != review['report_sha256']:
            return False
    if (value.get('acceptance') or {}).get('hash') != review.get('contract_hash'):
        return False
    for filename, expected in review['input_hashes'].items():
        path = artifact_path(workspace, filename)
        if not path or digest(path) != expected:
            return False
    reviewed_hashes = set(review['input_hashes'].values())
    sources = [f for s in value['steps'] for a in s['attempts']
               if any(artifact_path(workspace, p) == target for p in a.get('output_files', []))
               for f in (a.get('delivery_record') or {}).get('files', [])
               if f.get('role') in ('editable_source','source_archive')]
    return bool(sources) and all(f.get('sha256') in reviewed_hashes and artifact_path(workspace, f.get('path',''))
        and digest(artifact_path(workspace, f['path'])) == f['sha256'] for f in sources)
