"""Bounded control replies: execution success never hides a failed deliverable.

Full runtime results remain scoped, immutable and addressable. This projection
is for LLM control messages; the browser keeps the full project API.
"""
import json

from .acceptance import fingerprint, requirement_verdicts
from .project_skills import redact_memory, scoped_file
from .progress import clean_summary
from .handoff import blocking_checks

LIMIT = 8000  # Below pinned RigHaven's 12,000-character synopsis threshold.


def counts(items):
    return {status: sum(x.get('status') == status for x in items) for status in ('passed', 'failed', 'not_run')}


def has_blocking_checks(result):
    # harness_delegate computes this on the full validated handoff before the
    # display truncates it. A successor may be outside the short excerpt.
    total = result.get('blocking_failed_checks')
    if type(total) is int and total >= 0:
        return total > 0
    checks = result.get('checks', [])
    return bool(list(blocking_checks(checks))) or result.get('check_counts', {}).get('failed', 0) > sum(c.get('status') == 'failed' for c in checks)


def decision(result):
    review = result.get('quality_review') or {}
    delivery = result.get('delivery') or {}
    if not result.get('ok'):
        return 'execution_failed'
    if (delivery.get('technical_status') == 'needs_revision' or delivery.get('issues')
            or review.get('status') in ('failed', 'needs_revision') or has_blocking_checks(result)):
        return 'needs_revision'
    if review.get('status') == 'passed':
        return 'review_passed'
    return 'review_required' if result.get('outputs') else 'work_complete'


def continuation(review):
    """Route follow-up by observed defects, scope and available observation.

    This is guidance, never a replacement for the full acceptance verdict.
    In particular, an unsupported sensory check cannot be fixed by re-rendering.
    """
    if not review or not review.get('criteria'):
        return None
    checkpoint = review.get('checkpoint')
    criteria = [c for c in review['criteria'] if c.get('critical', True)]
    if checkpoint:
        criteria = [c for c in criteria if c.get('requirement_id') in checkpoint['requirement_ids']]
    failed = [c for c in criteria if c['status'] == 'failed']
    pending = [c for c in criteria if c['status'] == 'not_run']
    unavailable = set(review.get('unavailable_methods', []))
    waiting = [c for c in pending if (c.get('blocked_by') or c.get('method')) in unavailable]
    if failed:
        action = 'revise_checkpoint' if checkpoint else 'revise_product'
        instruction = 'Correggi solo i difetti osservati pertinenti a questa verifica, riusando i sorgenti. Non ripetere controlli che il collegamento non può eseguire.'
    elif pending and len(waiting) == len(pending):
        action = 'request_user_verification'
        instruction = 'Presenta il file esatto e indica i controlli da verificare con l’utente. Mantieni status=review; non rigenerare il prodotto né ripetere la stessa verifica con un collegamento privo della capacità necessaria.'
    elif pending or (not checkpoint and review.get('status') != 'passed'):
        action = 'verify_checkpoint' if checkpoint else 'verify_product'
        instruction = 'Completa le verifiche effettivamente disponibili sul file esistente; una verifica mancante non dimostra un difetto da correggere.'
    elif checkpoint:
        action = 'continue_production'
        instruction = 'La prova selezionata è superata: riusa il metodo e completa il prodotto richiesto, evitando un altro campione equivalente. Il contratto finale resta da soddisfare e verificare.'
    else:
        action = 'present_result'
        instruction = 'Presenta il prodotto e i suoi sorgenti; prima di dichiararlo pronto verifica anche i controlli tecnici della consegna.'
    return {'action': action, 'instruction': instruction, 'final_status': review.get('status'),
            'failed_requirement_ids': list(dict.fromkeys(c.get('requirement_id') for c in failed if c.get('requirement_id'))),
            'unavailable_methods': sorted({c.get('blocked_by') or c['method'] for c in waiting}),
            'next_actions':[{'method':item['method'],'reason':clean_summary(item['reason'],200),
                             'next_action':clean_summary(item['next_action'],250)} for item in review.get('observation_limits',[])[:3]]}


def project_view(project):
    if not project or project.get('archived'):
        return project
    value = {k: project.get(k) for k in ('id', 'status', 'summary', 'next_action', 'product_path',
             'quality_status', 'version_selection', 'attention', 'outcome', 'user_direction', 'user_control', 'memory', 'requirements', 'project_type', 'governance')}
    if project.get('designs'):value['designs'] = [{k:d.get(k) for k in ('id','title','tool','revision','source_path','sha256','state','bindings')} for d in project['designs']][:6]
    value['brief'] = clean_summary(project.get('brief'), 500)
    value['correction_focus'] = project.get('correction_focus', [])
    acceptance = project.get('acceptance') or {}
    value['acceptance'] = {k: acceptance.get(k) for k in ('hash', 'request_count', 'request_manifest')}
    value['acceptance']['criteria'] = [{k: c.get(k) for k in ('id', 'method', 'critical', 'origin')} |
            {'requirement': clean_summary(c.get('requirement'), 160)} for c in acceptance.get('criteria', [])]
    orientation = project.get('orientation') or {}
    value['orientation'] = {k: orientation.get(k) for k in ('total', 'counts', 'current', 'needs_briefing', 'history_count')}
    active = set(orientation.get('active_step_ids', [s['id'] for s in project.get('steps', [])]))
    value['steps'] = [{k: s.get(k) for k in ('id', 'agent', 'role_id', 'status')} |
            {'goal': clean_summary(s.get('goal'), 180)} for s in project.get('steps', []) if s['id'] in active][:16]
    value['roles'] = [{k: r.get(k) for k in ('id', 'title', 'tools', 'skills', 'skill_bindings', 'composition_version', 'skill', 'experience')} |
            {'mission': clean_summary(r.get('mission'), 160)} for r in project.get('roles', [])][:12]
    value['results'] = [{k: r.get(k) for k in ('path', 'role', 'delivery_id')} for r in project.get('results', [])[:4]]
    sample = project.get('latest_sample')
    value['latest_sample'] = {k: sample.get(k) for k in ('path', 'delivery_id', 'at', 'validated')} if sample else None
    value['deliveries'] = [{k: d.get(k) for k in ('id', 'title', 'technical_status', 'current', 'version_state')} for d in project.get('deliveries', [])[:3]]
    value['requirement_verdicts'] = requirement_verdicts(project.get('review_criteria', []))
    value['revision_actions'] = [fit(a, 160) for a in project.get('revision_actions', [])[:3]]
    if project.get('review_findings'):
        value['review_findings'] = [fit(f, 180) for f in project['review_findings'][:3]]
    value['revision_action_count'] = len(project.get('revision_actions', []))
    value['comparison'] = fit(project.get('comparison'), 120)
    value['continuation'] = continuation({'criteria': project.get('review_criteria', []),
        'status': project.get('quality_status'), 'checkpoint': project.get('review_checkpoint'),
        'unavailable_methods': project.get('review_unavailable_methods', []),
        'observation_limits': project.get('review_observation_limits', [])})
    strategy = project.get('strategy') or {}
    value['strategy'] = {k: strategy.get(k) for k in ('state', 'method', 'reason', 'user_action', 'stop_reason', 'record')}
    value['strategy']['alternatives'] = [fit(a, 160) for a in strategy.get('alternatives', [])]
    value['method_recovery'] = project.get('method_recovery')
    product = next((r for r in project.get('results', []) if r.get('path') == project.get('product_path')), None)
    show_sample = sample and (not product or sample.get('at','') > product.get('at',''))
    if product and not show_sample and project.get('status') in ('review', 'blocked', 'ready'):
        sources = [r for r in project.get('results', []) if product.get('delivery_id')
                   and r.get('delivery_id') == product['delivery_id'] and r.get('role') in ('source_archive', 'editable_source')]
        sources.sort(key=lambda r: r.get('role') != 'source_archive')
        value['presentation'] = {'paths': list(dict.fromkeys([product['path'], *[s['path'] for s in sources[:2]]])),
            'instruction': 'Prima di terminare o mettere in pausa il turno, chiama present_files sui file utili indicati. '
                'Se non approvati, etichettali come bozza/harness incompleto e spiega i difetti. La presenza nel pannello '
                'Progetto non sostituisce present_files e non dimostra il completamento del risultato richiesto.'}
    elif sample:
        sources = [r for r in project.get('results', []) if r.get('delivery_id') == sample.get('delivery_id')
                   and r.get('role') in ('source_archive', 'editable_source')]
        sources.sort(key=lambda r: r.get('role') != 'source_archive')
        value['presentation'] = {'paths': [sample['path'], *[s['path'] for s in sources[:2]]],
            'instruction': 'Presenta con present_files l’ultimo campione e i suoi sorgenti prima di continuare: descrivi cambiamenti e difetti rimasti, senza chiamarlo prodotto finale.'}
    return value


def delegate_view(result):
    # Preserve existing top-level fields on ordinary small replies.
    value = dict(result)
    value['decision'] = decision(result)
    review = result.get('quality_review') or {}
    value['check_counts'] = result.get('check_counts', counts(result.get('checks', [])))
    value['blocking_failed_checks'] = result.get('blocking_failed_checks', len(list(blocking_checks(result.get('checks', [])))))
    value['review_counts'] = counts(review.get('criteria', []))
    value['required_review_counts'] = counts([c for c in review.get('criteria', []) if c.get('critical',True)])
    value['quality_review'] = {**review, 'requirement_verdicts': requirement_verdicts(review.get('criteria', []))}
    value['continuation'] = continuation(review)
    if not review and has_blocking_checks(result):
        value['continuation'] = {'action': 'repair_known_defects',
            'instruction': 'Il produttore ha già dichiarato difetti concreti: correggi prima quelli sui sorgenti esistenti, senza una revisione completa equivalente. Isola la causa più importante con una prova economica prima di riesportare tutto. Se non migliora, rivaluta competenza o metodo, senza ripetere lo stesso incarico.',
            'final_status': 'needs_revision'}
    if review.get('criteria'):
        value['review_scope_instruction'] = 'Il verdetto aggregato comprende tutti i controlli dello stesso requisito: un passed locale non annulla failed o not_run. Un campione prova solo il risultato osservato; prima di estendere verifica i rischi e i difetti ancora aperti, senza abbassare il brief.'
    value['next_action'] = (review.get('revision_actions') or [{}])[0].get('action', '')
    if result.get('correction_focus'):
        value['correction_focus'] = result['correction_focus']
        value['team_instruction'] = ('Se reassess_role è true, rivaluta la competenza e il metodo: aggiorna il ruolo dinamico '
            'o assegna una correzione mirata a un ruolo pertinente. Non concentrare automaticamente tutti i difetti nello stesso autore. '
            'Conserva i file validi e verifica il difetto prima di estendere; nessun elenco fisso di professioni o strumenti obbligatori.')
    if review.get('status') == 'needs_revision':
        value['revision_instruction'] = ('Trasforma le correzioni in un incarico mirato sui file esistenti e verifica il prima/dopo. '
            'Non chiedere un altro procedi per una correzione già nello scopo autorizzato. Se il metodo non migliora, '
            'prova un metodo diverso pertinente; per dipendenze realmente mancanti spiega il limite. Non moltiplicare '
            'produzione o rigenerare parti già valide.')
    return value


def fit(value, limit=280):
    """Shrink descriptions, never file identities or status/requirement IDs."""
    if isinstance(value, str):
        return clean_summary(value, limit)
    if isinstance(value, list):
        return [fit(x, limit) for x in value]
    if isinstance(value, dict):
        identities = {'path', 'product_path', 'baseline_path', 'handoff_path', 'output_dir', 'details_path', 'report_path',
                      'id', 'requirement_id', 'role_id', 'delivery_id', 'sha256', 'details_sha256', 'verified_products', 'available_files', 'method_recovery', 'presentation'}
        return {k: v if k in identities else fit(v, limit) for k, v in value.items()}
    return value


def reply(workspace, payload, kind):
    full = redact_memory(payload)
    text = json.dumps(full, ensure_ascii=False)
    reference = scoped_file(workspace, 'control-results/' + kind + '-' + fingerprint(full) + '.json', text)
    value = {'project': project_view(full.get('project'))} if kind == 'plan' else delegate_view(full)
    if kind == 'plan':
        value['learning'] = full.get('learning', {})
    if kind == 'plan' and full.get('policy_book'):
        value['policy_book'] = full['policy_book']
    if kind == 'plan' and full.get('generation_capabilities'):
        value['generation_capabilities'] = full['generation_capabilities']
    value.update(details_path=reference['path'], details_sha256=reference['sha256'], details_reader='harness_read_context')
    if 'capability_policy' in full:
        value['capability_policy'] = full['capability_policy']
    if len(json.dumps(value, ensure_ascii=False)) <= LIMIT:
        return json.dumps(value, ensure_ascii=False)
    value = fit(value)
    if kind == 'delegate':
        # Put verdicts before inventories, not after pages of opening instructions.
        review = full.get('quality_review') or {}
        value['quality_review'] = {k: review.get(k) for k in ('status', 'product_path', 'report_path', 'checkpoint', 'unavailable_methods')}
        value['quality_review']['requirement_verdicts'] = requirement_verdicts(review.get('criteria', []))
        value['quality_review']['revision_actions'] = [fit(a, 160) for a in review.get('revision_actions', [])[:3]]
        value['quality_review']['revision_action_count'] = len(review.get('revision_actions', []))
        value['quality_review']['comparison'] = fit(review.get('comparison'), 120)
        value['quality_review']['criteria'] = [{k: c.get(k) for k in ('requirement_id', 'status', 'method', 'critical', 'scope')} |
            {'evidence': clean_summary(c.get('evidence'), 120)} for c in review.get('criteria', [])]
        value['outputs'] = [{k: f.get(k) for k in ('path', 'role', 'format')} for f in full.get('outputs', [])[:4]]
        value['output_count'] = full.get('output_count', len(full.get('outputs', [])))
        value['checks'] = sorted(value.get('checks', []), key=lambda c: c.get('status') == 'passed')[:5]
        value['warnings'] = value.get('warnings', [])[:3]
        value['review_notes'] = value.get('review_notes', [])[:4]
        value['available_files'] = value.get('available_files', [])[:4]
    required = True
    for limit in (160, 80):
        if len(json.dumps(value, ensure_ascii=False)) <= LIMIT:
            break
        value = fit(value, limit)
        if kind == 'plan':
            for key in ('roles', 'steps', 'results'):
                value['project'][key] = value['project'].get(key, [])[:4]
    if len(json.dumps(value, ensure_ascii=False)) > LIMIT:
        # All exceptions survive in the addressed full result; counters signal
        # that an omitted list is not evidence of success.
        keys = ('ok', 'decision', 'error', 'activity', 'delivery', 'checkpoint_reassessment', 'checkpoint','goal','instruction', 'check_counts', 'blocking_failed_checks', 'review_counts', 'required_review_counts',
                'attention', 'recovery', 'retry_blocked', 'experience', 'handoff_path', 'quality_review', 'next_action', 'revision_instruction', 'continuation', 'presentation')
        # A plan update echoes what the coordinator just wrote: its full board is
        # needed only when the runtime reports something to decide.
        if kind == 'plan':
            p = value.get('project') or {}
            value = {'project': {k: p.get(k) for k in ('id', 'status', 'summary', 'next_action', 'quality_status', 'version_selection', 'attention', 'method_recovery', 'presentation', 'continuation', 'governance')}}
            required = bool(p.get('attention') or p.get('method_recovery'))
        else:
            value = {k: value[k] for k in keys if k in value}
            if 'quality_review' in value:
                value['quality_review'].pop('criteria', None)
        value.update(details_path=reference['path'], details_sha256=reference['sha256'],
                     details_required=required, details_reader='harness_read_context',
                     instruction='Usa harness_read_context con details_path e details_sha256 prima di decidere; le liste omesse non sono controlli superati.'
                     if required else 'Piano registrato come richiesto: prosegui; leggi i dettagli solo per riesaminare attività, ruoli o risultati.')
    # A malicious/oversize input must not turn into an unbounded control message.
    if len(json.dumps(value, ensure_ascii=False)) > LIMIT:
        value = {k: value.get(k) for k in ('ok', 'decision', 'check_counts', 'review_counts', 'details_path', 'details_sha256')}
        value['details_required'] = required
        value['details_reader'] = 'harness_read_context'
    return json.dumps(value, ensure_ascii=False)
