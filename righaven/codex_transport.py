"""Codex SSE transport that preserves API errors before the stream closes."""
import json

import httpx


def request_codex(headers, payload):
    completed = None
    items = {}
    with httpx.Client(timeout=300) as client:
        with client.stream('POST', 'https://chatgpt.com/backend-api/codex/responses',
                           headers=headers, json=payload) as response:
            if response.is_error:
                # HTTPX cannot read an unread body after leaving this context.
                response.read()
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith('data:'):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get('type')
                if kind == 'response.output_item.done':
                    index, item = event.get('output_index'), event.get('item')
                    if isinstance(index, int) and index >= 0 and isinstance(item, dict):
                        items[index] = item
                elif kind == 'response.completed':
                    completed = event.get('response')
                    break
                elif kind in ('response.failed', 'response.incomplete', 'error'):
                    data = event if kind == 'error' else event.get('response', {})
                    details = (data.get('error') or data.get('incomplete_details') or data) if isinstance(data, dict) else {}
                    if not isinstance(details, dict):
                        details = {'message': str(details)}
                    message = details.get('message') or details.get('reason') or 'Richiesta Codex interrotta'
                    raise RuntimeError('Codex API ' + kind + ': ' + str(message))
    if not isinstance(completed, dict):
        raise RuntimeError('Codex API stream ended without response.completed event')
    if items:
        output = list(completed.get('output') or [])
        output.extend([None] * max(0, max(items) + 1 - len(output)))
        for index, item in items.items():
            if not isinstance(output[index], dict):
                output[index] = item
        completed = {**completed, 'output': [item for item in output if isinstance(item, dict)]}
    return completed
