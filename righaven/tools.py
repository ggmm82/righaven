"""RigHaven tool: delegate one task using the specialist's configured CLI."""
from langchain.tools import tool
from righaven_core.tools.types import Runtime
from righaven_core.config.paths import get_paths
from righaven_core.runtime.user_context import resolve_runtime_user_id
from .docker_runtime import delegate
from .projects import archive_plan, create_plan, execute_step, read_project, revise_step, set_policy_plan, sync_acceptance, sync_project_context
from .project_brief import briefing_issue
import json


def workspace_for(runtime):
    thread = runtime.config.get('configurable', {}).get('thread_id')
    if not thread:
        raise ValueError('La delega richiede una conversazione RigHaven')
    user = resolve_runtime_user_id(runtime)
    paths = get_paths()
    paths.ensure_thread_dirs(thread, user_id=user)
    return paths.sandbox_user_data_dir(thread, user_id=user)


def experience_root(runtime):
    return get_paths().user_dir(resolve_runtime_user_id(runtime)) / 'righaven-experience'


@tool('harness_skills',parse_docstring=True)
def harness_skills(runtime:Runtime,query:str='',name:str='',reference:str='SKILL.md',offset:int=0)->str:
    """Discover authorized native skills or read one method/reference in pages.

    Also lists owner environment profiles and all authorized tool capabilities.
    Skills describe methods and tool expertise; available tools and runtime
    images are separate. Read relevant methods before composing a project role.

    Args:
        runtime: Injected RigHaven runtime.
        query: Search words in skill names and descriptions; empty returns a compact catalog.
        name: Exact authorized native skill name to read; empty searches metadata only.
        reference: SKILL.md or a relative file under references/ in that skill.
        offset: Character offset; follow next_offset until null.
    """
    from .capability_policy import runtime_policy
    from .skill_composition import inventory,package_revision,environment_inventory
    from pathlib import Path
    import hashlib
    policy=runtime_policy(runtime)
    if not name:
        return json.dumps({**inventory(policy,query),'environments':environment_inventory(policy)},ensure_ascii=False)
    source=policy.get('skill_sources',{}).get(name)
    if not source or name not in policy.get('skill_names',[]):raise ValueError('Skill non autorizzata nel profilo')
    root=Path(source).resolve();path=root/reference
    if '..' in Path(reference).parts or (reference!='SKILL.md' and not reference.startswith('references/')) or not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file() or path.stat().st_size>200000:
        raise ValueError('Riferimento della skill non valido')
    revision=package_revision(source);text=path.read_text()
    if type(offset) is not int or offset<0 or offset>len(text):raise ValueError('Offset non valido')
    end=min(len(text),offset+8000)
    return json.dumps({'name':name,'reference':reference,'revision':revision,'sha256':hashlib.sha256(text.encode()).hexdigest(),
                       'content':text[offset:end],'next_offset':end if end<len(text) else None},ensure_ascii=False)


@tool('harness_read_context', parse_docstring=True)
def harness_read_context(runtime: Runtime, path: str, sha256: str, offset: int = 0) -> str:
    """Read a hash-verified project context reference in bounded pages.

    Use for details_path/details_sha256, saved requests, compiled roles and design source_path/sha256 references.
    Native read_file cannot read hidden project context. Follow next_offset until null.

    Args:
        runtime: Injected RigHaven runtime.
        path: Exact virtual path supplied by a project context reference.
        sha256: Exact SHA-256 supplied with that reference.
        offset: Character offset; zero initially, then the returned next_offset.
    """
    from .context_reader import read_context
    return json.dumps(read_context(workspace_for(runtime), path, sha256, offset), ensure_ascii=False)


def preserve_experience(workspace, runtime):
    from .experience import collect
    from .lessons import pending, propose_findings, automatic
    try:
        thread = (getattr(runtime, 'config', None) or {}).get('configurable', {}).get('thread_id')
        saved = collect(workspace, experience_root(runtime), thread)
        proposals = propose_findings(experience_root(runtime), thread)
        if proposals:
            sync_project_context(workspace, experience_root=experience_root(runtime))
        if saved or proposals:
            from .audit_log import append
            append(workspace, 'Memoria', 'Fonti esperienza archiviate', 'completed',
                   detail=f'{saved} nuove fonti; {len(proposals)} proposte. Archiviazione e apprendimento sono distinti.')
        sources = pending(experience_root(runtime), limit=3, source_thread=thread)
        return {'saved': saved, 'proposed_lessons': len(proposals), 'pending': len(pending(experience_root(runtime))),
                'technical_active_in_library': len(automatic(experience_root(runtime))),
                'notice': 'saved conta fonti archiviate, non lezioni apprese. Solo lezioni tecniche verificate o metodi accettati entrano nelle skills pertinenti.',
                'sources_to_evaluate': [{k: s.get(k) for k in ('id', 'criterion', 'status')} for s in sources],
                'instruction': 'Usa harness_lessons per valutare queste evidenze: generalizza poche cause/procedure utili, anche dai fallimenti, oppure motiva perché non sono trasferibili. Non inventare benefici né trasferire fatti specifici nelle skills. Un metodo proposto richiede accettazione; un test operativo serve solo per attivare automaticamente conoscenza tecnica.'}
    except (OSError, ValueError, TypeError):
        return {'error': 'Esperienza non archiviata: conserva il volume dati e riprova il recupero dalla scheda Esperienza.'}


def interaction_id(runtime):
    messages = (getattr(runtime, 'state', None) or {}).get('messages', [])
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        kind = message.get('type', message.get('role')) if isinstance(message, dict) else getattr(message, 'type', '')
        if kind in ('human', 'user'):
            identifier = message.get('id') if isinstance(message, dict) else getattr(message, 'id', None)
            return str(identifier or ('human-' + str(index)))[:150]
    return ''


def source_turn(runtime):
    config = (getattr(runtime, 'config', None) or {}).get('configurable') or {}
    if 'righaven_user_turn' in config:
        return config['righaven_user_turn'] or ''
    return interaction_id(runtime)


def user_requests(runtime):
    from .project_skills import request_text
    captured = (getattr(runtime, 'config', None) or {}).get('configurable', {}).get('righaven_user_messages')
    context = getattr(runtime, 'context', None) or {}
    is_subagent = context.get('is_subagent', False) if isinstance(context, dict) else getattr(context, 'is_subagent', False)
    if is_subagent:
        # Child HumanMessages are instructions generated by the coordinator.
        # Inherit only the gateway's actual user input, never relabel those tasks.
        if not isinstance(captured, list):
            return []
        return [request_text(s) for s in captured if isinstance(s, str) and s.strip()]
    result = []
    for message in (getattr(runtime, 'state', None) or {}).get('messages', []):
        kind = message.get('type', message.get('role')) if isinstance(message, dict) else getattr(message, 'type', '')
        if kind not in ('human', 'user'):
            continue
        content = message.get('content', '') if isinstance(message, dict) else getattr(message, 'content', '')
        if isinstance(content, list):
            content = '\n'.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
        if isinstance(content, str) and content.strip():
            result.append(request_text(content))
    for text in captured if isinstance(captured, list) else []:
        if isinstance(text, str) and text.strip() and request_text(text) not in result:
            result.append(request_text(text))
    return result


def lesson_reply(runtime, value):
    """Keep learning reports below upstream synopsis limits, with full private detail."""
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= 8000:
        return text
    from .acceptance import fingerprint
    from .project_skills import scoped_file
    document = scoped_file(workspace_for(runtime), 'learning-results/' + fingerprint(value) + '.json', text)
    compact = [{k: source.get(k) for k in ('id', 'status', 'tools', 'impact')} |
               {'criterion': str(source.get('criterion', ''))[:160], 'evidence': str(source.get('evidence', ''))[:300]}
               for source in value.get('pending_sources', [])[:6]]
    result = {'saved_lesson': value.get('saved_lesson'), 'decision': value.get('decision'),
              'pending_sources': compact, 'source_count': len(value.get('pending_sources', [])),
              'details_path': document['path'], 'details_sha256': document['sha256'],
              'details_reader': 'harness_read_context',
              'instruction': 'Usa harness_read_context con details_path e details_sha256 prima di generalizzare; non trasferirne i fatti specifici nelle skills.'}
    while compact and len(json.dumps(result, ensure_ascii=False)) > 8000:
        compact.pop()
    return json.dumps(result, ensure_ascii=False)


@tool('harness_lessons', parse_docstring=True)
def harness_lessons(runtime: Runtime, source_ids_json: str = '', lesson_json: str = '', dismiss_reason: str = '', impact_json: str = '', current_project_only: bool = False) -> str:
    """Generalize saved evidence into conditional reusable lessons, never project facts.

    Read without arguments to inspect up to six pending evidence records. Extract
    the transferable cause, procedure, verification and limits, including CLI usage
    findings reported by sandboxes. Inspect suggested_lesson, evidence_files and
    producer_method; distinguish reported operations from independent verification.
    Omit names,
    story content, file paths and project choices. Group related observations.
    A user preference is not technical verification; preserve that distinction.
    Save only individual lessons with a useful transferable insight, not every
    observation. Prioritize substantial improvements, not trivial tips. Distinguish
    measured gains from observations and hypotheses; never invent percentages.
    Dismiss unhelpful sources with a reason; keep their evidence.
    Production methods require individual owner acceptance in the Lessons panel.
    Tool-operation knowledge is activated by runtime-checked tests, never by model self-approval.
    Accepted lessons guide future roles only when relevant and compatible with tool versions.
    Do not block useful production on the learning backlog.

    Args:
        runtime: Injected RigHaven runtime.
        current_project_only: Restrict pending evidence to this conversation; use when evaluating its old observations without producing new work.
        source_ids_json: JSON list of one to six real saved evidence IDs.
        impact_json: Optional JSON level major/minor/unknown, basis measured/observed/hypothesis and reason grounded in the selected evidence. No fabricated measurements. This ranks proposals, not a product quality certificate.
        dismiss_reason: Instead of saving a lesson, explain why the selected source IDs do not warrant one. Do not combine with lesson_json.
        lesson_json: JSON category (production_method for realization strategy, tool_operation for CLI usage), title, applies_when, procedure (list), verification (list), limits and tools (installed IDs or empty for a general principle). Conditions and limits are required; no facts of the source project.
    """
    from .lessons import learn, pending, dismiss
    root = experience_root(runtime)
    preserve_experience(workspace_for(runtime), runtime)
    thread = (getattr(runtime,'config',None) or {}).get('configurable',{}).get('thread_id') if current_project_only else None
    if dismiss_reason:
        if lesson_json:
            raise ValueError('Salva o scarta la singola lezione, non entrambe')
        dismiss(root, json.loads(source_ids_json), dismiss_reason)
        return lesson_reply(runtime, {'decision': 'not_generalized', 'pending_sources': pending(root,source_thread=thread)})
    if bool(source_ids_json) != bool(lesson_json):
        raise ValueError('Indica sia le fonti sia la lezione generale')
    identifier = learn(root, json.loads(source_ids_json), json.loads(lesson_json), json.loads(impact_json) if impact_json else None) if lesson_json else None
    if identifier:
        sync_project_context(workspace_for(runtime), experience_root=root)
    return lesson_reply(runtime, {'saved_lesson': identifier, 'pending_sources': pending(root,source_thread=thread),
                       'instruction': 'Conserva solo la lezione generale e condizionale; le fonti restano separate e non dimostrano più di quanto verificato.'})


@tool('harness_plan', parse_docstring=True)
def harness_plan(runtime: Runtime, brief: str = '', steps_json: str = '',
                project_type: str = '', omissions_json: str = '{}', revise_step_id: str = '',
                archive: bool = False, summary: str = '', next_action: str = '', status: str = '',
                product_path: str = '', requirements_json: str = '', criteria_json: str = '', roles_json: str = '', memory_json: str = '', outcome_json: str = '', strategy_json: str = '', designs_json: str = '', policies_json: str = '') -> str:
    """Maintain a concise, adaptive production workspace and visible user status.

    Read without arguments. Update the brief, activity board or current status as
    the work evolves; existing attempts and files are preserved. Activities may
    be reordered, added, reassigned or skipped. depends_on is an input hint, not
    a blocking pipeline. Compile project-specific professional roles from the actual brief; installed tools are capabilities, not a list of professions.
    Discover capabilities with harness_skills before composing roles. Roles without tools or skills require capability_rationale explaining how the base runtime can produce and verify the product.
    Prefer a representative preview at the intended finish; shorten its scope before lowering fidelity. Improve the observed bottleneck with focused specialist work.
    Avoid long plans and technical recaps: summary and next_action appear beside
    the chat input. Use purpose=delivery on the final integration to check media.
    The runtime enforces Brief -> Execution Plan + Policy Plan -> policy-aware
    assignments -> harness_validate -> delivery; governance.phase shows the stage.

    Args:
        runtime: Injected RigHaven runtime.
        brief: Desired product and key acceptance criteria.
        steps_json: Optional JSON list of id, agent, goal, depends_on and optional status pending/review/skipped; updates existing activities by ID.
        project_type: custom or animated_video; the latter defaults to video with audio, without forcing a fixed team.
        omissions_json: Compatibility field for explicit user exclusions, such as soundcraft for a silent video.
        revise_step_id: Reopen only this activity; keep other results usable.
        archive: Archive an inactive abandoned project, preserving files.
        summary: One short sentence explaining the current practical work to the user.
        next_action: One short sentence describing the next useful result or action.
        status: clarifying, working, review, ready, blocked or idle.
        product_path: Existing verified final product to show prominently; ready requires it.
        requirements_json: Media acceptance requirements such as {"audio":true,"video":true}; follow the user's brief.
        roles_json: JSON roles compiled for this project: id, title, mission, expertise, procedure, checks, deliverables, skills (exact authorized native names discovered with harness_skills), tools (available catalog IDs, optional), inputs and risks; optional network: up to eight {domain, reason} the role must reach beyond the model provider (for example fonts or a public dataset), granted only when the installation restricts worker egress. Selected skill requirements add their tools automatically. Roles are dynamic, not tool identities; scope and package versions are recorded. Each role requires capability_rationale: explain why the selected capabilities can construct its actual content/model, not merely export the delivery format; consider relevant owner environments and justify simpler alternatives. Do not assign every available tool or impose a fixed team.
        memory_json: JSON object with project-specific decisions, facts, questions and asset references; merge top-level keys, keep evidence and uncertainty explicit.
        outcome_json: JSON intended result with title, result, format (delivery form, not necessarily a file extension), use, quality, constraints, assumptions, questions. Questions are at most three decisive missing user choices; ask them with ask_clarification, then replace the object with the real answers and questions empty before delegating. Do not ask again for choices already explicit in the brief. tool_options lists up to four tool decisions when several catalog tools could produce the result: id, decision, 2–4 options (id, label, tools, pros, cons), recommended option and recommendation_reason, chosen empty. Present them with ask_clarification and set chosen only after the user's reply; production waits for every choice and roles cannot use tools of rejected options.
        strategy_json: Optional method selection, especially after a failed sample: method, reason, state (exploring/selected/needs_user), up to three alternatives with method, reason, tools, status (candidate/tested/unavailable) and evidence_paths (existing workspace files required for tested). To pause for user help include stop_reason (missing_input/capability_limit/user_choice/budget) and concrete user_action. A quality failure alone cannot establish an external blocker. Revisit team assumptions before requesting assets; changing method does not authorize lowering user requirements.
        designs_json: Optional JSON list of visual models: id, title, tool, source_path, optional preview_path, bindings (element_id with step_id/role_id/criterion_id/delivery_id) and expected_revision when updating. Register existing editable design files; read current revisions first and preserve user edits. No fixed diagram notation is required.
        policies_json: Policy Plan beside the Execution Plan: JSON list of optional Policy Book sheets that apply, each with id, reason and optional steps (activity IDs; empty means every production activity). [] records that no optional sheet applies. Mandatory sheets are always added by the runtime. Production assignments wait until the plan is settled.
        criteria_json: JSON acceptance criteria for any product: id, requirement, method (content, visual, listening, structural, functional, reference), critical and reference_paths. Optional origin=user requires source_quote copied from actual user messages; origin=proposal identifies team choices. Proposals remain checked until explicitly revised; never weaken user requirements to pass. Preserve requested references; no invented substitutions.
    """
    workspace = workspace_for(runtime)
    from .capability_policy import runtime_policy, public, require_tools
    policy = runtime_policy(runtime)
    if strategy_json:
        from .strategy import check_capability_choice
        check_capability_choice(json.loads(strategy_json), policy)
    if roles_json:
        from .project_brief import rejected_tools
        excluded = rejected_tools((read_project(workspace) or {}).get('outcome'))
        for spec in json.loads(roles_json):
            require_tools(policy, spec.get('tools', []))
            if excluded & set(spec.get('tools', [])):
                raise ValueError('Il ruolo ' + str(spec.get('id')) + ' usa programmi di alternative non scelte dall’utente: '
                                 + ', '.join(sorted(excluded & set(spec.get('tools', [])))) + '. Rispetta la scelta registrata nel brief.')
            if not isinstance(spec.get('capability_rationale'),str) or not spec['capability_rationale'].strip():
                raise ValueError('Consulta harness_skills e indica capability_rationale per ogni ruolo: quali capacità costruiscono il contenuto/modello, quali lo impaginano o esportano e quali lo verificano; confronta gli ambienti pertinenti. Il formato finale non giustifica da solo la scelta dello strumento. Anche il solo runtime base richiede una motivazione.')
    learning = {}
    requests = user_requests(runtime)
    if read_project(workspace):
        sync_acceptance(workspace, requests, json.loads(criteria_json) if criteria_json else None)
    if status == 'ready' and not ((read_project(workspace) or {}).get('acceptance') or {}).get('user_requests'):
        raise ValueError('Impossibile dichiarare concluso il prodotto senza la richiesta originale dell’utente nel contesto verificabile.')
    if archive:
        value = archive_plan(workspace, brief)
    elif revise_step_id:
        value = revise_step(workspace, revise_step_id, brief or summary or next_action)
    elif any((brief, steps_json, summary, next_action, status, product_path, requirements_json, project_type, criteria_json, roles_json, memory_json, outcome_json, strategy_json)):
        value = create_plan(workspace, brief, json.loads(steps_json or '[]'), project_type,
            json.loads(omissions_json), summary=summary, next_action=next_action, status=status,
            product_path=product_path, requirements=json.loads(requirements_json) if requirements_json else None,
            outcome=json.loads(outcome_json) if outcome_json else None, source_turn=source_turn(runtime))
    else:
        value = read_project(workspace)
    if value and not value.get('archived'):
        sync_acceptance(workspace, requests, json.loads(criteria_json) if criteria_json else None)
        if strategy_json:
            create_plan(workspace, '', [], strategy=json.loads(strategy_json), status='blocked' if status == 'blocked' else '')
        if designs_json:
            from .project_design import register
            register(workspace,json.loads(designs_json),set(policy['allowed']))
        learning = preserve_experience(workspace, runtime)
        sync_project_context(workspace, json.loads(roles_json) if roles_json else None, json.loads(memory_json) if memory_json else None, experience_root=experience_root(runtime),skill_policy=policy)
        if policies_json:
            set_policy_plan(workspace, json.loads(policies_json))
        value = read_project(workspace)
    if value and not value.get('archived'):
        # The user board contains all versions. Repeating its entire inventory
        # used to overflow tool context and hide the actual product/brief.
        value = {**value, 'results': value.get('results', [])[:8],
                 'deliveries': value.get('deliveries', [])[:5]}
    from .control_memory import reply
    from .state import team
    from .acceptance import generation_capabilities
    from .policy_book import catalog
    return reply(workspace, {'project': value, 'learning': learning, 'capability_policy': public(policy), 'policy_book': catalog(),
        'generation_capabilities': generation_capabilities(team('squad')['engine'], (value or {}).get('user_direction'))}, 'plan')


@tool('harness_delegate', parse_docstring=True)
def harness_delegate(agent: str, task: str, runtime: Runtime, step_id: str = '', purpose: str = 'work', role_id: str = '') -> str:
    """Assign focused work to any useful RigHaven specialist, reusing available files.

    Activities are flexible. step_id is optional and an activity is created when
    needed. A failed colleague, optional check or missing handoff must not block
    useful review or integration of existing files. Inspect partial work rather
    than rebuilding it. Provider quota/auth failures pause work and require the
    shared provider to become available; never retry the same outage in a loop.
    Use purpose=preview for a small complete prototype before expensive renders;
    purpose=integration assembles available parts; purpose=delivery validates the
    final media requirements in the worker. Deliver editable sources and genuine
    opening evidence. Independent activities may run concurrently within the configured CPU/RAM and worker limits. Issue independent harness_delegate calls together; wait for required colleague outputs before dependent work.

    Args:
        agent: Use workspace for a dynamic project role; its selected skills/tools determine the runtime. Historical tool specialist IDs remain compatible with old chats.
        role_id: ID of a project-specific compiled role created with harness_plan roles_json. Required for workspace; uses its procedure and tool skills.
        task: Concrete result, pertinent input paths and acceptance checks; avoid broad rediscovery.
        runtime: Injected RigHaven runtime.
        step_id: Optional activity identifier, reusable for targeted revisions.
        purpose: work, preview, review, integration or delivery.
    """
    return delegate_step(agent, task, runtime, step_id=step_id, purpose=purpose, role_id=role_id)


def delegate_step(agent, task, runtime, *, step_id='', purpose='work', role_id='', policy_sheet=None):
    """One assignment; policy_sheet turns a review into that sheet's final validation."""
    workspace = workspace_for(runtime)
    requests = user_requests(runtime)
    if not read_project(workspace):
        create_plan(workspace, requests[0] if requests else task, [])
    sync_acceptance(workspace, requests)
    project = read_project(workspace) or {}
    from .capability_policy import runtime_policy, require_tools
    policy = runtime_policy(runtime)
    issue = briefing_issue(project.get('outcome'))
    if issue:
        create_plan(workspace, '', [], status='clarifying', summary='Prima definiamo il risultato da ottenere.',
                    next_action='Rispondi alle domande sul risultato e sulla forma della consegna.')
        return json.dumps({'ok': False, 'needs_briefing': True, 'error': issue,
                           'outcome': project.get('outcome'), 'instruction': 'Usa ask_clarification per le scelte decisive mancanti; aggiorna harness_plan(outcome_json) prima di riprovare. Non è un errore del provider e non richiede tentativi ripetuti.'}, ensure_ascii=False)
    from .state import team
    profile = team('squad')
    request_id = interaction_id(runtime)
    preserve_experience(workspace, runtime)
    sync_project_context(workspace, experience_root=experience_root(runtime),skill_policy=policy)
    project = read_project(workspace) or {}
    if not role_id and step_id:
        role_id = next((s.get('role_id', '') for s in project.get('steps', []) if s['id'] == step_id), '')
    role = next((r for r in project.get('roles', []) if r['id'] == role_id), None) if role_id else None
    if (role_id and not role) or (agent == 'workspace' and not role):
        raise ValueError('Definisci prima il ruolo concreto con harness_plan roles_json')
    require_tools(policy, ([agent] if agent != 'workspace' else []) + (role or {}).get('tools', []))
    from .project_brief import rejected_tools
    excluded = rejected_tools(project.get('outcome')) & set((role or {}).get('tools', []) + ([agent] if agent != 'workspace' else []))
    if excluded:
        raise ValueError('L’utente ha scelto un’altra alternativa: questo incarico userebbe ' + ', '.join(sorted(excluded)) + '. Aggiorna il ruolo.')
    requirements = project.get('requirements', {}) if purpose == 'delivery' else {}
    policy_review = {}
    if policy_sheet is not None and policy_sheet['final_checks'] != 'acceptance':
        from .policy_book import contract
        policy_review = {'policy_review': {'sheet': policy_sheet['id'], 'revision': policy_sheet['revision'],
                                           'contract': contract(policy_sheet, None)}}
    result = json.loads(execute_step(workspace, agent, task, step_id,
        lambda instructions, started=None: delegate(agent, instructions, workspace,
            tool_call_id=getattr(runtime, 'tool_call_id', None), on_started=started,
            requirements=requirements, purpose=purpose, acceptance=project.get('acceptance'), role=role,
            capability_policy=policy, **policy_review), provider={k: profile[k] for k in ('engine', 'model', 'connection_id') if k in profile},
        purpose=purpose, request_id=request_id, role=role, policy_sheet=policy_sheet))
    try:
        return delegation_reply(workspace, runtime, result, project, profile, purpose)
    except Exception as error:
        # The assignment is already recorded: never report it as failed or invite a re-run.
        from .progress import clean_summary
        from .audit_log import append
        append(workspace, 'Coordinatore', 'Riepilogo dell’incarico non disponibile', 'failed', detail=clean_summary(error))
        return json.dumps({k: result[k] for k in ('ok', 'activity', 'output_dir', 'error', 'checkpoint', 'policy_violations') if k in result}
                          | {'available_files': result.get('available_files', [])[:20], 'summary_unavailable': True,
                             'instruction': 'L’incarico è registrato con il suo esito: non rilanciarlo. Il riepilogo completo non è disponibile; '
                                            'leggi i file indicati o lo stato con harness_plan.'}, ensure_ascii=False)


def delegation_reply(workspace, runtime, result, project, profile, purpose):
    """Compact coordinator view of a recorded assignment."""
    experience = preserve_experience(workspace, runtime)
    handoff = result.get('handoff') or {}
    from .handoff import blocking_checks
    from .control_memory import counts
    from .progress import clean_summary
    compact = {k: result[k] for k in ('ok', 'duplicate', 'activity', 'output_dir', 'attention', 'recovery', 'retry_blocked', 'checkpoint_reassessment','goal','instruction',
        'product_verified', 'verified_products', 'available_results', 'policy_violations', 'policy_compliance', 'checkpoint') if k in result}
    compact.update(error=clean_summary(result.get('error', '')),
        check_counts=counts(handoff.get('checks', [])),
        blocking_failed_checks=len(list(blocking_checks(handoff.get('checks', [])))),
        available_files=result.get('available_files', [])[:20],
        source_status=handoff.get('delivery', {}).get('source_status'),
        outputs=[{**{k: clean_summary(f.get(k, '')) for k in ('path', 'role', 'format', 'open_with', 'editability')},
                  'reopen': {'status': (f.get('reopen') or {}).get('status', 'not_run'),
                             'evidence': clean_summary((f.get('reopen') or {}).get('evidence', ''))},
                  'limitations': [clean_summary(s) for s in f.get('limitations', [])[:3]]}
                 for f in handoff.get('delivery', {}).get('files', [])[:20]],
        checks=[{'name': clean_summary(c.get('name')), 'status': c.get('status'),
                 **{k: c[k] for k in ('scope','superseded_by') if k in c},
                 'evidence': clean_summary(c.get('evidence'))} for c in sorted(handoff.get('checks', []), key=lambda c: c.get('status') == 'passed')[:10]],
        warnings=[clean_summary(w) for w in handoff.get('warnings', [])[:5]],
        review_notes=result.get('review_notes', [])[:8])
    if result.get('output_dir') and handoff:
        compact['handoff_path'] = result['output_dir'] + '/handoff.json'
    record = result.get('delivery_record') or {}
    compact['delivery'] = {k: record.get(k) for k in ('id', 'title', 'technical_status', 'issues', 'source_status', 'finalization_pending', 'reused_archive_checks')}
    compact['quality_review'] = result.get('quality_review')
    compact['correction_focus'] = (read_project(workspace) or {}).get('correction_focus', [])
    compact['learning_review'] = result.get('learning_review')
    from .acceptance import capabilities
    compact['experience'] = experience
    compact['verification_capabilities'] = capabilities(profile['engine'])
    from .acceptance import generation_capabilities
    current_direction = (read_project(workspace) or {}).get('user_direction')
    compact['user_direction'] = current_direction
    if current_direction != project.get('user_direction'):
        compact['direction_changed'] = 'L’utente ha cambiato le scelte durante questo incarico: rileggi harness_plan e ripianifica prima di produrre o approvare. Conserva i file validi.'
    compact['generation_capabilities'] = generation_capabilities(profile['engine'], current_direction)
    from .control_memory import reply, counts
    compact['check_counts'] = counts(handoff.get('checks', []))
    compact['output_count'] = len(handoff.get('delivery', {}).get('files', []))
    if result.get('ok') and purpose in ('preview', 'delivery'):
        files = handoff.get('delivery', {}).get('files', [])
        from .handoff import product_files
        primary = next((f['path'] for f in product_files(files)), None)
        if primary:
            sources = sorted((f for f in files if f.get('role') in ('source_archive', 'editable_source')),
                             key=lambda f: f['role'] != 'source_archive')
            compact['presentation'] = {'paths': list(dict.fromkeys([primary, *[f['path'] for f in sources[:2]]])),
                'instruction': 'Presenta questi file con present_files prima della prossima delega. Spiega cosa è cambiato e i difetti rimasti. Un campione o un prodotto non approvato resta una bozza; non dichiararlo finito e non nascondere la versione disponibile mentre continui le correzioni.'}
    return reply(workspace, compact, 'delegate')


async def _harness_delegate_async(agent: str, task: str, runtime: Runtime, step_id: str = '', purpose: str = 'work', role_id: str = '') -> str:
    from .cancellation import call
    return await call(harness_delegate.func, agent=agent, task=task, runtime=runtime,
                      step_id=step_id, purpose=purpose, role_id=role_id)


# Keep the synchronous function for direct callers; LangGraph awaits this
# coroutine, so an explicit run cancellation reaches the Docker worker too.
harness_delegate.coroutine = _harness_delegate_async


@tool('harness_delegate_batch',parse_docstring=True)
def harness_delegate_batch(assignments_json:str,runtime:Runtime)->str:
    """Run independent role assignments concurrently, each with isolated staging.

    Use for genuinely independent contributions. Dependent work waits for its
    prerequisite activities and consumes their published outputs in a later batch.

    Args:
        assignments_json: JSON list of 2–8 objects with agent, task, role_id and optional step_id/purpose, as for harness_delegate.
        runtime: Injected RigHaven runtime.
    """
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    assignments=json.loads(assignments_json)
    allowed={'agent','task','role_id','step_id','purpose'}
    if not isinstance(assignments,list) or not 2<=len(assignments)<=8 or any(not isinstance(a,dict) or set(a)-allowed or not a.get('agent') or not a.get('task') for a in assignments):
        raise ValueError('Indica da 2 a 8 incarichi indipendenti con agente, ruolo e compito')
    named=[a['step_id'] for a in assignments if a.get('step_id')]
    if len(set(named))!=len(named):raise ValueError('Non eseguire due volte la stessa attività nel gruppo')
    def invoke(assignment):
        try:return json.loads(harness_delegate.func(runtime=runtime,**assignment))
        except Exception as error:return {'ok':False,'error':str(error)[:1000]}
    # Submit the whole bounded batch to the live FIFO/budget admission layer.
    # A second pool limit captured here would ignore later configuration changes
    # and hide pending assignments from cancellation and queue monitoring.
    with ThreadPoolExecutor(max_workers=len(assignments),thread_name_prefix='rh-team') as pool:
        futures=[pool.submit(copy_context().run,invoke,a) for a in assignments]
        results=[f.result() for f in futures]
    return json.dumps({'ok':all(r.get('ok') for r in results),'assignments':results},ensure_ascii=False)


@tool('harness_validate', parse_docstring=True)
def harness_validate(runtime: Runtime, role_id: str, task: str = '') -> str:
    """Run the final multi-policy validation of the finished product before delivery.

    Requires a completed Execution Plan and a product_path. The runtime first checks
    delivery integrity, then runs one separate review per Policy Plan sheet that has
    no valid verdict for this exact product: independent sheets in parallel, dependent
    sheets after their prerequisites. All violations are returned together. Delivery
    (status=ready) is refused until every sheet passes. Correct violations on the
    sources, deliver a new version, then validate again; a passed sheet is reused.

    Args:
        runtime: Injected RigHaven runtime.
        role_id: Reviewer role compiled with harness_plan roles_json; it must not have produced the product.
        task: Optional guidance for the reviewers: product context, references and what to inspect.
    """
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    from . import policy_workflow
    from .projects import governance_state, save_policy_validation
    workspace = workspace_for(runtime)
    value = governance_state(workspace)
    if not policy_workflow.governed(value):
        raise ValueError('Questo progetto è precedente al Policy Book: usa purpose=review per la revisione di qualità')
    stage = policy_workflow.phase(value)
    if stage in ('briefing', 'planning'):
        raise ValueError('Completa prima brief, Execution Plan e Policy Plan (fase attuale: ' + stage + ')')
    if stage == 'execution':
        open_steps = [s['id'] for s in value['steps'] if s.get('kind') != 'validation' and s['status'] not in policy_workflow.SETTLED]
        raise ValueError('La validazione finale riguarda il prodotto finito: ' + (
            'attività ancora aperte: ' + ', '.join(open_steps) if open_steps else 'indica product_path del prodotto consegnato con purpose=delivery'))
    if not any(r['id'] == role_id for r in value.get('roles', [])):
        raise ValueError('Indica il ruolo revisore compilato con harness_plan roles_json')
    from .projects import artifact_path
    product = artifact_path(workspace, value.get('product_path', ''))
    authors = {a.get('role_id') for s in value['steps'] if s.get('kind') != 'validation' for a in s['attempts']
               if product and any(artifact_path(workspace, p) == product for p in a.get('output_files', []))}
    if role_id in authors:
        raise ValueError('La validazione finale richiede un revisore indipendente: il ruolo ' + role_id + ' ha prodotto il file da validare')
    report = policy_workflow.validation(workspace, value)
    runs = []
    if report['integrity']['status'] == 'passed':
        sheets = {s['id']: s for s in value['policy_plan']['sheets']}
        to_run = [sheets[s['id']] for s in report['sheets'] if s['status'] == 'pending']
        guidance = task.strip() or 'Valida il prodotto finito ' + value.get('product_path', '') + ' senza modificarlo.'

        def review(sheet):
            try:
                result = json.loads(delegate_step('workspace', guidance, runtime, step_id='policy-' + sheet['id'],
                                                  purpose='review', role_id=role_id, policy_sheet=sheet))
            except Exception as error:
                result = {'ok': False, 'error': str(error)[:500]}
            return {'sheet': sheet['id'], 'ok': bool(result.get('ok')), 'error': result.get('error', '')}
        for wave in policy_workflow.waves(to_run):
            current = {s['id']: s['status'] for s in report['sheets']}
            ready = [s for s in wave if all(current.get(d) == 'passed' for d in s['depends_on'])]
            runs += [{'sheet': s['id'], 'ok': False, 'error': 'In attesa delle sheet da cui dipende: ' + ', '.join(s['depends_on'])}
                     for s in wave if s not in ready]
            if ready:
                with ThreadPoolExecutor(max_workers=len(ready), thread_name_prefix='rh-policy') as pool:
                    runs += [f.result() for f in [pool.submit(copy_context().run, review, s) for s in ready]]
            report = policy_workflow.validation(workspace, governance_state(workspace))
    saved = save_policy_validation(workspace, report)
    instruction = {'passed': 'Tutte le policy sono superate: dichiara la consegna con harness_plan(status=ready).',
                   'failed': 'Correggi tutte le violazioni elencate sui sorgenti, consegna una nuova versione e ripeti harness_validate.',
                   'blocked': 'Il prodotto non supera il controllo di integrità: correggi la consegna con purpose=delivery.',
                   }.get(report['status'], 'Alcune verifiche non sono state eseguite o richiedono un metodo non disponibile: '
                                           'non dichiarare la consegna; spiega all’utente cosa manca.')
    return json.dumps({'ok': report['status'] == 'passed', 'status': report['status'], 'integrity': report['integrity'],
                       'sheets': saved['sheets'], 'reviews': runs, 'instruction': instruction}, ensure_ascii=False)


async def _harness_validate_async(runtime: Runtime, role_id: str, task: str = '') -> str:
    from .cancellation import call
    return await call(harness_validate.func, runtime=runtime, role_id=role_id, task=task)


harness_validate.coroutine = _harness_validate_async
