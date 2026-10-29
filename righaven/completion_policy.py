"""Decide whether a production turn has a justified stopping point."""


def needs_continuation(project):
    if not project or project.get('status') in ('ready', 'clarifying'):
        return False
    if any((project.get('user_control') or {}).get(k) for k in ('paused','deliver_now')):
        return False
    attention = project.get('attention') or {}
    if attention.get('code') in ('provider_quota', 'provider_auth', 'resource_memory', 'work_cancelled'):
        return False
    strategy = project.get('strategy') or {}
    if strategy.get('state') == 'needs_user' and strategy.get('stop_reason') and strategy.get('user_action'):
        return False
    # Do not turn a genuinely unavailable observation into another render.
    criteria = [c for c in project.get('review_criteria', []) if c.get('critical', True)]
    pending = [c for c in criteria if c.get('status') != 'passed']
    unavailable = project.get('review_unavailable_methods', [])
    if pending and all(c.get('status') == 'not_run' and (c.get('blocked_by') or c.get('method')) in unavailable for c in pending):
        return False
    return True


def production_call(call):
    """Review-only batches must not authorize new production on completion."""
    import json
    args=call.get('args') or {}
    if call.get('name')=='harness_delegate':return args.get('purpose','work')!='review'
    if call.get('name')!='harness_delegate_batch':return False
    try:
        assignments=json.loads(args.get('assignments_json','[]'))
        return isinstance(assignments,list) and any(isinstance(a,dict) and a.get('purpose','work')!='review' for a in assignments)
    except (ValueError,TypeError):return False
