"""User brief and directions: acceptance requests, visual direction and pause control."""
import json
import uuid

from .progress import utcnow, workspace_key
from .state import atomic_json
from .acceptance import contract, fingerprint
from .project_skills import compact_acceptance, save_requests, read_document
from .project_store import locked, load, workspace_path


def sync_acceptance(workspace, requests, criteria=None):
    if not requests:return
    from .project_controls import operational_resume
    requests=[r for r in requests if not operational_resume(r)]
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            return
        old = value.get('acceptance') or {}
        direction = value.get('user_direction')
        if direction:
            requests = [*requests, 'Scelta esplicita dell’utente dal pannello progetto: ' + json.dumps(direction, ensure_ascii=False)]
        previous = old.get('user_requests', [])
        documents = json.loads(read_document(workspace, old['request_manifest'])) if old.get('request_manifest') else []
        documents=[d for d in documents if not operational_resume(read_document(workspace,d))]
        previous=[r for r in previous if not operational_resume(r)]
        if not documents and previous:
            # Recover the original from complete human history after upgrading the 4000-char copy.
            if requests and requests[0].startswith(previous[0]) and len(requests[0]) > len(previous[0]):
                previous[0] = requests[0]
            requests = previous + [r for r in requests if r not in previous]
        if not requests and not documents:return
        documents, manifest = save_requests(workspace, requests, documents)
        selected = documents[:1] + documents[-8:] if len(documents) > 9 else documents
        # Provenance must also resolve a quoted choice outside the compact
        # first/latest previews. The contract still exposes only those previews.
        texts = [read_document(workspace, d) for d in documents]
        if criteria is None:
            criteria = [c for c in old.get('criteria', []) if c['id'] != 'request_fidelity']
        updated = compact_acceptance(contract(texts, criteria))
        updated['hash'] = fingerprint({'contract': updated['hash'], 'history': [d['sha256'] for d in documents]})
        updated.update(request_documents=selected, request_manifest=manifest, request_count=len(documents))
        for rule in updated['criteria']:
            if any(workspace_path(workspace, p) is None for p in rule['reference_paths']):
                raise ValueError('I riferimenti devono appartenere alla conversazione')
        if old.get('hash') == updated['hash']:
            return
        value['acceptance'] = updated
        if value.get('status') == 'ready':
            value['status'] = 'review'
        value.pop('user_acceptance', None)
        atomic_json(folder / 'project.json', value)


def set_user_direction(workspace, visual_approach, instructions):
    """Only the owner API writes this choice; coordinator plans cannot replace it."""
    if visual_approach not in ('unspecified', 'generated', 'vector', 'mixed', 'automatic'):
        raise ValueError('Tecnica visiva non riconosciuta')
    if not isinstance(instructions, str) or len(instructions) > 2000:
        raise ValueError('Istruzioni entro 2000 caratteri')
    from .project_skills import request_text
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            raise ValueError('Definisci prima il progetto')
        old = value.get('user_direction') or {}
        if old.get('visual_approach') == visual_approach and old.get('instructions', '') == instructions.strip():
            return _direction_result(value)
        direction = {'visual_approach': visual_approach, 'instructions': request_text(instructions.strip()),
                     'revision': old.get('revision', 0) + 1, 'updated_at': utcnow()}
        value['user_direction'] = direction
        value.pop('user_acceptance', None)
        if value.get('status') == 'ready':
            value['status'] = 'review'
        value['updated_at'] = utcnow()
        # Invalidate old approvals immediately, even before the next coordinator turn.
        if value.get('acceptance'):
            value['acceptance']['hash'] = fingerprint({'previous': value['acceptance']['hash'], 'user_direction': direction})
        atomic_json(folder / 'project.json', value)
        return _direction_result(value)


def _direction_result(value):
    return {'user_direction': value['user_direction'],
            'running_step_ids': [s['id'] for s in value.get('steps', []) if s['status'] == 'running'],
            'instruction': 'Scelta salvata per i prossimi incarichi. Le fasi già avviate conservano il loro incarico: interrompile dal pannello Attività per cambiare subito. Riporta questa scelta in chat per chiedere al coordinatore la ripianificazione.'}


def set_user_control(workspace, paused):
    if type(paused) is not bool:
        raise ValueError('Indica se mettere in pausa il progetto')
    with locked(workspace) as folder:
        value = load(folder, workspace)
        if not value:
            value = {'id': uuid.uuid4().hex, 'workspace_key': workspace_key(workspace),
                     'brief': 'Progetto da definire', 'project_type': 'custom', 'created_at': utcnow(),
                     'steps': [], 'requirements': {}}
        previous = value.get('user_control') or {}
        if previous.get('paused') != paused or previous.get('deliver_now'):
            value['user_control'] = {'paused': paused, 'revision': previous.get('revision', 0) + 1, 'updated_at': utcnow()}
            value['updated_at'] = utcnow()
            atomic_json(folder / 'project.json', value)
        return value.get('user_control')


def assert_user_allows_work(value, *, allow_delivery=False):
    if (value.get('user_control') or {}).get('deliver_now') and not allow_delivery:
        raise ValueError('Consegna ora richiesta: non avviare altri incarichi. Mostra i risultati disponibili e attendi nuove istruzioni.')
    if (value.get('user_control') or {}).get('paused'):
        raise ValueError('Progetto in pausa su richiesta dell’utente: attendi Riprendi dal pannello, senza avviare altre deleghe.')
