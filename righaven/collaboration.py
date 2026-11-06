"""Owner decisions and reusable recipe proposals over the existing project method.

A coordinator proposes and tests. Only the owner chooses a method or saves a
recipe; a successful command or a generated file never counts as owner approval.
"""
import json
from pathlib import Path

from .acceptance import fingerprint
from .project_store import locked, load
from .state import atomic_json
from .progress import utcnow
from .strategy import proof_path
from .source_packages import digest

GUIDANCE = '''In open chat, build the method with the user. Explain useful work in plain language; do not narrate internal phase IDs, policy statuses or tool names. Present the final result once, after tool calls return, with usable links and actual verification limits; do not repeat a long final answer in a tool-call message. Clarify only missing choices that materially change the result (audience, delivery form, constraints and success criteria). Explain your recommended approach in plain language. When approaches have meaningful trade-offs, offer at most three alternatives, with advantages, limitations and cost; do not invent alternatives for routine actions. Record them using harness_plan(strategy_json), not a second plan. If the user must choose, set state=needs_user, stop_reason=user_choice and a concrete user_action, then pause before production. Respect the latest owner method decision. Test the chosen approach on a representative sample, show evidence and explain what changed before extending it. Never turn assumptions into owner requirements. When the user changes direction or requests a new revision after delivery, call harness_method(objective) quoting their latest request verbatim; this opens a new objective while retaining the prior result as a base and archiving old recipe gates. Never make the owner restart a recipe or repeat completed phases just to evolve a result. Connections are optional resources, usable without recipes; inspect authorized connections, never request passwords in chat. A method may become a reusable recipe only on the owner's request: propose a generalized, editable draft through harness_method(recipe_json). Do not copy project-specific facts, IDs, private data, credentials or output paths into that draft. A draft is private and unapproved until the owner reviews and saves it; publication is a separate choice.'''


def signature(project):
    return fingerprint({'strategy': project.get('strategy'), 'contract': (project.get('acceptance') or {}).get('hash')})


def view(workspace):
    with locked(workspace) as folder:
        project = load(folder, workspace) or {}
        return _view(project, folder)


def _view(project, folder):
    candidate = _candidate(folder)
    stamp = signature(project)
    return {'signature': stamp, 'strategy': project.get('strategy'), 'decision': project.get('method_decision'),
            'history': project.get('method_decisions', [])[-10:],
            'recipe_available': bool(candidate and candidate.get('signature') == stamp),
            'recipe_stale': bool(candidate and candidate.get('signature') != stamp)}


def choose(workspace, expected, choice, note, allowed_tools):
    if not isinstance(note, str) or len(note) > 1500:
        raise ValueError('Method feedback must be within 1500 characters')
    with locked(workspace) as folder:
        project = load(folder, workspace)
        if not project or not project.get('strategy'):
            raise ValueError('Ask the coordinator to propose a method first')
        if signature(project) != expected:
            raise ValueError('The method changed; reload before choosing')
        strategy = project['strategy']
        if strategy.get('request_hash') != (project.get('acceptance') or {}).get('hash'):
            raise ValueError('The goal changed; ask for an updated method')
        main = next((a for a in strategy.get('alternatives', []) if a['method'] == strategy['method']), None)
        candidates = [main or {'method': strategy['method'], 'reason': strategy['reason'], 'tools': []}, *strategy.get('alternatives', [])]
        if not isinstance(choice, int) or not 0 <= choice < len(candidates):
            raise ValueError('Choose one of the proposed methods')
        selected = candidates[choice]
        if selected.get('status') == 'unavailable' or set(selected.get('tools', [])) - set(allowed_tools):
            raise ValueError('This method uses unavailable capabilities; ask for an alternative')
        previous = project.get('method_decision') or {}
        if previous.get('signature') == expected and previous.get('method') == selected['method'] and previous.get('note') == note.strip():
            return _view(project, folder)
        decision = {'method': selected['method'], 'reason': selected['reason'], 'tools': selected.get('tools', []),
                    'note': note.strip(), 'at': utcnow(), 'signature': expected}
        project['method_decision'] = decision
        project['method_decisions'] = [*project.get('method_decisions', []), decision][-40:]
        # Keep evidence in the existing strategy. The coordinator adopts the
        # chosen alternative on its next turn; this records an owner instruction.
        project['status'] = 'review'
        project['next_action'] = 'Apply the owner method choice and test the next useful result'
        atomic_json(folder / 'project.json', project)
    from .audit_log import append
    append(workspace, 'User', 'Method chosen', 'completed', selected['method'])
    return view(workspace)


def _candidate(folder):
    path = folder / 'method-recipe.json'
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 100000:
        raise ValueError('Invalid method recipe draft')
    return json.loads(path.read_text())


def propose(workspace, owner, draft, allowed_skills, allowed_tools):
    from .recipes import compose, DRAFT_TEXT, TEXT_LISTS
    # Validate the same contract used by the human editor, including secret
    # rejection and currently enabled capabilities, before recording a draft.
    recipe = compose(draft, owner, allowed_skills, known_tools=set(allowed_tools))
    text = recipe['en']
    clean = {**{k: text[k] for k in (*DRAFT_TEXT, *TEXT_LISTS)},
             'phases': text['phases'], 'skills': recipe['skills'], 'tools': recipe['tools'],
             'environment': recipe['environment'], 'keywords': recipe['keywords'],
             'guidance': recipe['workflow']['guidance']}
    with locked(workspace) as folder:
        project = load(folder, workspace) or {}
        decision = project.get('method_decision')
        if not decision:
            raise ValueError('The owner must choose the method before consolidating it')
        strategy = project.get('strategy') or {}
        if strategy.get('request_hash') != (project.get('acceptance') or {}).get('hash'):
            raise ValueError('The goal changed; ask for an updated method')
        proofs = [a for a in strategy.get('alternatives', []) if a['method'] == decision['method'] and a['status'] == 'tested']
        if not proofs or not any(a.get('evidence') for a in proofs):
            raise ValueError('Test the chosen method and record evidence before proposing a recipe')
        evidence = [e for a in proofs for e in a['evidence']]
        recorded = {str(proof_path(workspace, path))
                    for step in project.get('steps', []) for attempt in step.get('attempts', [])
                    if attempt.get('status') == 'completed' and attempt.get('validated') and not attempt.get('failed_checks')
                    for path in attempt.get('output_files', [])}
        for item in evidence:
            path = proof_path(workspace, item['path'])
            if str(path) not in recorded:
                raise ValueError('Method evidence must come from a completed validated assignment')
            if digest(path) != item['sha256']:
                raise ValueError('Method evidence changed; test again before proposing a recipe')
        candidate = {'signature': signature(project), 'created_at': utcnow(), 'draft': clean,
                     'evidence': evidence, 'method': decision['method']}
        atomic_json(folder / 'method-recipe.json', candidate)
    return {'proposed': True, 'saved': False, 'shared': False,
            'instruction': 'Ask the owner to review the recipe draft in Method. Only their Save action creates a private recipe.'}


def recipe_draft(workspace):
    with locked(workspace) as folder:
        project = load(folder, workspace) or {}
        candidate = _candidate(folder)
        if not candidate or candidate['signature'] != signature(project):
            raise ValueError('No current recipe proposal; ask the coordinator to prepare it')
        for item in candidate['evidence']:
            if digest(proof_path(workspace, item['path'])) != item['sha256']:
                raise ValueError('Method evidence changed; refresh the proposal')
        return candidate['draft']
