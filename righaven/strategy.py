"""Evidence-bound method choices, without a fixed production pipeline."""
import json
from pathlib import Path

from .acceptance import fingerprint
from .project_skills import read_document, request_text, scoped_file
from .source_packages import digest


def check_capability_choice(value, policy):
    """Do not turn an excluded tool into an obligatory production method."""
    if not isinstance(value, dict):
        raise ValueError('Il metodo deve essere un oggetto JSON')
    alternatives = value.get('alternatives', [])
    if not isinstance(alternatives, list) or any(not isinstance(a, dict) or
            not isinstance(a.get('tools', []), list) or
            any(not isinstance(t, str) for t in a.get('tools', [])) for a in alternatives):
        raise ValueError('Alternative: oggetti con una lista di strumenti')
    allowed = set(policy.get('allowed', []))
    for item in alternatives:
        if item.get('status') in ('candidate', 'tested') and set(item.get('tools', [])) - allowed:
            raise ValueError('Il metodo proposto usa strumenti disabilitati: scegli capacità consentite.')
    if value.get('state') == 'needs_user' and value.get('stop_reason') == 'capability_limit' and policy.get('blocked'):
        # A blocked app only rules out that method. Assess a permitted method,
        # including workspace-only work, before claiming the result is blocked.
        assessed = [a for a in alternatives if not (set(a.get('tools', [])) - allowed)]
        if not assessed or any(a.get('status') == 'candidate' for a in assessed):
            raise ValueError('Uno strumento disabilitato è una scelta dell’utente, non un obbligo da riattivare. '
                'Valuta prima un metodo con gli strumenti consentiti e registralo in alternatives con ragione concreta. '
                'Prova un piccolo campione se fattibile; se manca davvero una capacità, spiega il limite senza '
                'abbassare i requisiti o imporre la riattivazione.')


def proof_path(workspace, value):
    root = Path(workspace).resolve()
    path = Path(value)
    if not path.is_relative_to(root) and path.is_relative_to('/mnt/user-data'):
        path = root / path.relative_to('/mnt/user-data')
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('La prova del metodo deve essere un file esistente della conversazione')
    return path.resolve()


def validate(workspace, value, apps, request_hash):
    if not isinstance(value, dict) or len(json.dumps(value).encode()) > 12000:
        raise ValueError('Descrivi sinteticamente il metodo e fino a tre alternative')
    state = value.get('state', 'exploring')
    if state not in ('exploring', 'selected', 'needs_user'):
        raise ValueError('Stato del metodo: exploring, selected o needs_user')
    result = {'state': state, 'request_hash': request_hash}
    for key, limit in (('method', 800), ('reason', 800), ('user_action', 800)):
        text = value.get(key, '')
        if not isinstance(text, str) or len(text) > limit or key != 'user_action' and not text.strip():
            raise ValueError('Il metodo richiede method e reason concreti; testi entro 800 caratteri')
        result[key] = request_text(text.strip())
    stop = value.get('stop_reason', '')
    if stop not in ('', 'missing_input', 'capability_limit', 'user_choice', 'budget'):
        raise ValueError('Motivo della pausa non riconosciuto')
    result['stop_reason'] = stop
    alternatives = value.get('alternatives', [])
    if not isinstance(alternatives, list) or len(alternatives) > 3:
        raise ValueError('Valuta al massimo tre alternative pertinenti; nessuna squadra obbligatoria')
    known = {a['id'] for a in apps}
    result['alternatives'] = []
    for item in alternatives:
        if not isinstance(item, dict):
            raise ValueError('Alternativa non valida')
        candidate = {}
        for key in ('method', 'reason'):
            text = item.get(key, '')
            if not isinstance(text, str) or not text.strip() or len(text) > 800:
                raise ValueError('Ogni alternativa richiede metodo e ragione concreta')
            candidate[key] = request_text(text.strip())
        status = item.get('status')
        if status not in ('candidate', 'tested', 'unavailable'):
            raise ValueError('Alternativa: candidate, tested o unavailable')
        selected = item.get('tools', [])
        if not isinstance(selected, list) or len(selected) > 4 or any(not isinstance(t, str) or t not in known for t in selected):
            raise ValueError('Indica soltanto strumenti installati pertinenti al metodo')
        paths = item.get('evidence_paths', [])
        if not isinstance(paths, list) or len(paths) > 3 or any(not isinstance(p, str) for p in paths):
            raise ValueError('Indica al massimo tre prove per alternativa')
        if status == 'tested' and not paths:
            raise ValueError('Un metodo dichiarato provato richiede un file di evidenza')
        evidence = []
        for filename in paths:
            path = proof_path(workspace, filename)
            evidence.append({'path': '/mnt/user-data/' + path.relative_to(Path(workspace).resolve()).as_posix(), 'sha256': digest(path)})
        candidate.update(status=status, tools=selected, evidence=evidence)
        result['alternatives'].append(candidate)
    if state == 'needs_user' and (not stop or not result['user_action']):
        raise ValueError('Per coinvolgere l’utente indica motivo e azione concreta che sblocca il lavoro')
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    result['record'] = scoped_file(workspace, 'strategies/' + fingerprint(result) + '.json', serialized)
    return result


def recovery(workspace, project):
    """A failed method alone cannot establish an external production blocker.

    Operational errors already carry their own attention and recovery action.
    This gate only handles a coordinator declaring a quality failure blocked.
    It does not launch jobs, relax acceptance or claim a candidate will succeed.
    """
    from .project_brief import orientation
    active = set(orientation(project)['active_step_ids'])
    contract = (project.get('acceptance') or {}).get('hash')
    failed = any(a.get('failed_checks') or (a.get('quality_review') or {}).get('status') == 'needs_revision'
                 for s in project.get('steps', []) if s['id'] in active for a in s.get('attempts', [])
                 if not a.get('context',{}).get('contract') or a['context']['contract'] == contract)
    stale_stop = (project.get('strategy') or {}).get('state') == 'needs_user' and (project.get('strategy') or {}).get('request_hash') != contract
    if (not failed and not stale_stop) or project.get('attention'):
        return None
    strategy = project.get('strategy') or {}
    valid = strategy.get('request_hash') == (project.get('acceptance') or {}).get('hash')
    candidates = any(a['status'] == 'candidate' for a in strategy.get('alternatives', []))
    try:
        if strategy:
            read_document(workspace, strategy['record'])
        valid = valid and all(digest(proof_path(workspace, p['path'])) == p['sha256']
            for a in strategy.get('alternatives', []) for p in a.get('evidence', []))
    except (OSError, ValueError, KeyError):
        valid = False
    stop = strategy.get('stop_reason')
    if (valid and strategy.get('state') == 'needs_user' and strategy.get('user_action')
            and stop and (not candidates or stop in ('budget', 'user_choice'))
            and (strategy.get('alternatives') or stop in ('budget', 'user_choice'))):
        return None
    return {'code': 'method_selection_required',
            'message': 'Il campione è insufficiente; il metodo va rivalutato prima di dichiarare una dipendenza esterna.',
            'instruction': 'Rileggi le richieste originali: outcome.assumptions sono scelte provvisorie, non vincoli imposti dall’utente. '
                'Distingui difetto locale, asset inadeguato, impostazione errata e limite reale della capacità. '
                'Conserva il metodo e i sorgenti validi; cambia metodo solo con evidenze del limite o di un beneficio sul campione. '
                'Aggiorna strategy_json e i ruoli pertinenti senza ricostruire automaticamente il prodotto. '
                'Distingui creazione degli asset, integrazione e resa finale: uno strumento che importa un asset non ne garantisce l’authoring. '
                'Sul requisito fallito prova il percorso completo fino al risultato osservabile, conservando il campione migliore. '
                'Prova un campione piccolo entro lo scopo autorizzato, senza abbassare qualità o cambiare il prodotto richiesto. '
                'Se occorrono davvero input, capacità, budget o una scelta dell’utente, registra state=needs_user, stop_reason, '
                'alternative valutate e user_action concreta. Non ripetere tentativi identici né dichiarare impossibilità generale.'}
