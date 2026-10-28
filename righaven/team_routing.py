"""Route chat to the coordinator profile and keep work alive after disconnect."""
import json
import re
import uuid
from .project_skills import request_text

RUN_PATH = re.compile(r'^/api/(?:threads/[^/]+/)?runs(?:/(?:stream|wait))?/?$')


def shared_run(body):
    if not isinstance(body, dict):
        return body
    result = dict(body)
    # Missing browser options must not inherit the Gateway's cancel default.
    # An explicit API cancellation policy remains supported; Stop uses its own endpoint.
    result.setdefault('on_disconnect', 'continue')
    config = dict(body.get('config') or {})
    context = dict(body.get('context') or {})
    agent_name = context.get('agent_name') or (config.get('configurable') or {}).get('agent_name')
    # Native Agent model/skills/SOUL resolution remains owned by RigHaven.
    result['context'] = context if agent_name else {**context, 'model_name': 'rh-codex'}
    if not agent_name and isinstance(config.get('configurable'), dict) and 'model_name' in config['configurable']:
        config['configurable'] = {**config['configurable'], 'model_name': 'rh-codex'}
        result['config'] = config
    # Ground the contract in the submitted human input, not synthetic HumanMessages
    # created later by planners/subagents. Authorization remains in the native
    # endpoint; nothing is written to a workspace before it runs.
    inputs = body.get('input') or {}
    messages = inputs.get('messages', []) if isinstance(inputs, dict) else []
    requests = []
    for message in messages if isinstance(messages, list) else []:
        if isinstance(message, dict) and message.get('role', message.get('type')) in ('user', 'human'):
            content = message.get('content', '')
        elif isinstance(message, str):
            content = message
        else:
            continue
        if isinstance(content, list):
            content = '\n'.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
        if isinstance(content, str) and content.strip():
            requests.append(request_text(content))
    if config.get('configurable') is None or isinstance(config.get('configurable'), dict):
        captured = requests[:1] + requests[-8:] if len(requests) > 9 else requests
        config['configurable'] = {**(config.get('configurable') or {}), 'righaven_user_messages': captured}
        config['configurable']['righaven_user_turn'] = uuid.uuid4().hex if captured else None
        config['configurable']['righaven_agent_name'] = agent_name
        result['config'] = config
    return result


class TeamRoutingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path, method = scope.get('path', ''), scope.get('method')
        if method == 'POST' and RUN_PATH.fullmatch(path):
            chunks = []
            while True:
                message = await receive()
                if message['type'] != 'http.request':
                    return
                chunks.append(message.get('body', b''))
                if not message.get('more_body'):
                    break
            body = b''.join(chunks)
            try:
                body = json.dumps(shared_run(json.loads(body))).encode()
            except (ValueError, TypeError):
                pass  # Native request validation reports malformed input.
            scope = {**scope, 'headers': [(k, v) for k, v in scope['headers'] if k != b'content-length']}
            scope['headers'].append((b'content-length', str(len(body)).encode()))
            consumed = False
            original_receive = receive
            async def replaced_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                return await original_receive()
            receive = replaced_receive
        if method == 'GET' and path.rstrip('/') == '/api/models':
            start, chunks = None, []
            original_send = send
            async def filtered_send(message):
                nonlocal start
                if message['type'] == 'http.response.start':
                    start = message
                elif message['type'] == 'http.response.body':
                    chunks.append(message.get('body', b''))
                    if message.get('more_body'):
                        return
                    body = b''.join(chunks)
                    if start['status'] == 200:
                        try:
                            data = json.loads(body)
                            data['models'] = [m for m in data.get('models', []) if m.get('name') == 'rh-codex']
                            body = json.dumps(data).encode()
                        except (ValueError, TypeError, KeyError):
                            pass
                    headers = [(k, v) for k, v in start['headers'] if k != b'content-length']
                    await original_send({**start, 'headers': [*headers, (b'content-length', str(len(body)).encode())]})
                    await original_send({'type': 'http.response.body', 'body': body})
            send = filtered_send
        await self.app(scope, receive, send)
