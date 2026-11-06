"""Validate coordinator calls before execution; never turn unknown writes into reads."""
import copy
import hashlib
import json


def closed_schema(schema):
    value = copy.deepcopy(schema)
    def close(node):
        if isinstance(node, dict):
            if 'properties' in node:
                node.setdefault('additionalProperties', False)
            for child in node.values():
                close(child)
        elif isinstance(node, list):
            for child in node:
                close(child)
    close(value)
    return value


def argument_error(arguments, schema):
    from jsonschema import Draft202012Validator
    errors = sorted(Draft202012Validator(closed_schema(schema)).iter_errors(arguments), key=lambda e: str(list(e.path)))
    if not errors:
        return None
    # Do not echo arbitrary argument values, credentials or full validation payloads.
    error = errors[0]
    return {'ok': False, 'changed': False, 'code': 'invalid_tool_arguments',
            'field': '.'.join(map(str, error.path)), 'rule': error.validator,
            'allowed_fields': sorted(schema.get('properties', {})),
            'instruction': 'The operation did not run. Use exactly the declared arguments. Read the current phase and its next_action; do not rewrite phase statuses or mark activities running.'}


def signature(call):
    def normalize(value):
        if isinstance(value, str):
            try:
                return normalize(json.loads(value))
            except ValueError:
                return value
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        return value
    return hashlib.sha256(json.dumps([call.get('name'), normalize(call.get('args', {}))], sort_keys=True).encode()).hexdigest()


def repeated_failures(messages, call):
    """Only the current user turn counts; a later user decision permits recovery."""
    count = 0
    key = signature(call)
    for message in reversed(messages):
        kind = message.get('type', message.get('role')) if isinstance(message, dict) else getattr(message, 'type', '')
        if kind in ('human', 'user'):
            break
        extra = message.get('additional_kwargs', {}) if isinstance(message, dict) else getattr(message, 'additional_kwargs', {})
        if extra.get('righaven_control_progress'):
            break
        if extra.get('righaven_failed_call') == key:
            count += 1
    return count
