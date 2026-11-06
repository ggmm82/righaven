"""Keep imperfect worker notes as unverified evidence, never active lessons."""
import json
from pathlib import Path
from .acceptance import fingerprint
from .project_skills import redact_memory
from .progress import utcnow


def preserve_note(workspace, attempt, manifest, manifest_hash, capture_key, candidate, installed, source_thread, error):
    if (not isinstance(candidate, dict) or not candidate
            or not any(isinstance(candidate.get(key), str) and candidate[key].strip() for key in ('finding','lesson'))):
        return None
    text = json.dumps(redact_memory(candidate), ensure_ascii=False)
    tool = candidate.get('tool')
    known = {tool: installed[tool]} if isinstance(tool, str) and tool in installed else {}
    path = '/mnt/user-data/' + manifest.relative_to(Path(workspace).resolve()).as_posix()
    observation = redact_memory({
        'kind':'unstructured_tool_note', 'capture_key':capture_key, 'source_thread':source_thread,
        'criterion':'Appunto da generalizzare' + (': '+tool if known else ''),
        'status':'needs_generalization', 'method':'worker_report', 'evidence':text[:1500],
        'corrections':[], 'tools':known, 'scope_known':bool(known),
        'source_report':path, 'report_sha256':manifest_hash,
        'evidence_files':[{'path':path,'sha256':manifest_hash}],
        'technical_validation':{'status':'not_recorded'},
        'impact':{'level':'unknown','basis':'hypothesis','reason':'Nota del worker ancora da generalizzare e verificare.'},
        'limitations':['Il file dimostra che l’appunto è stato salvato, non che il suo contenuto sia corretto.',
                       'Formato non conforme: '+str(error)[:300]+'. Nessuna lezione attivata automaticamente.']})
    observation['origin_id'] = fingerprint(observation)
    return {'id':fingerprint(observation), 'at':attempt.get('finished_at') or utcnow(), 'observation':observation}
