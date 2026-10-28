"""RigHaven decisions over agy's official JSON-schema output, not a Google API."""
import json
import uuid


def text_content(content):
    if isinstance(content, str):
        return content
    result = []
    for block in content or []:
        if isinstance(block, str):
            result.append(block)
        elif block.get('type') in ('text', 'text_delta'):
            result.append(block.get('text', ''))
        else:
            raise ValueError('Antigravity chat: contenuto non testuale non supportato; delega il file allo specialista')
    return '\n'.join(result)


def request(messages, model, tools=(), tool_choice=None):
    allowed = {t['function']['name']: t['function'] for t in tools}
    names = set(allowed)
    required = tool_choice in ('required', 'any') if isinstance(tool_choice, str) else False
    if tool_choice == 'none':
        names = set()
    elif isinstance(tool_choice, dict):
        name = tool_choice.get('function', {}).get('name')
        if name not in names:
            raise ValueError('Strumento Antigravity richiesto non disponibile')
        names, required = {name}, True
    elif tool_choice not in (None, 'auto', 'required', 'any'):
        raise ValueError('Scelta degli strumenti Antigravity non valida')
    variants = [{'type': 'object', 'additionalProperties': False, 'properties': {
        'name': {'type': 'string', 'enum': [name]},
        'args': allowed[name].get('parameters', {'type': 'object'})},
        'required': ['name', 'args']} for name in sorted(names)]
    calls = {'type': 'array', 'minItems': 1 if required else 0,
             'items': {'anyOf': variants} if variants else {'type': 'object'}}
    if not variants:
        calls['maxItems'] = 0
    schema = {'type': 'object', 'additionalProperties': False, 'properties': {
        'content': {'type': 'string'}, 'tool_calls': calls}, 'required': ['content', 'tool_calls']}
    records, ids = [], set()
    for item in messages:
        record = {'role': item['type'], 'content': text_content(item['content'])}
        if item['type'] == 'ai':
            record['tool_calls'] = item.get('tool_calls', [])
            ids.update(c['id'] for c in record['tool_calls'])
        if item['type'] == 'tool':
            if item['tool_call_id'] not in ids:
                raise ValueError('Risultato senza chiamata corrispondente')
            record['tool_call_id'] = item['tool_call_id']
        records.append(record)
    prompt = ('Sei il coordinatore RigHaven nella conversazione JSON seguente. '
              'Rispetta le istruzioni di sistema della conversazione. Usa il tool nativo finish per consegnare una decisione conforme allo schema JSON fornito, inclusi content e tool_calls. '
              'tool_calls richiede l’esecuzione degli strumenti di RigHaven, non dichiara che siano già eseguiti. '
              'Usa i risultati reali presenti nello storico. Non creare file o usare strumenti operativi locali. L’unico tool nativo da usare è finish; le tool_calls dentro la decisione saranno eseguite da RigHaven dopo la fine di questo processo.\n'
              + json.dumps({'messages': records, 'available_tools': [allowed[n] for n in sorted(names)], 'output_schema': schema}, ensure_ascii=False))
    return {'model': model, 'prompt': prompt, 'schema': schema}


def response(value, tools=()):
    if not isinstance(value.get('content'), str) or not isinstance(value.get('tool_calls'), list):
        raise RuntimeError('Decisione Antigravity non valida')
    allowed = {t['function']['name'] for t in tools}
    calls = []
    for call in value['tool_calls']:
        if call.get('name') not in allowed or not isinstance(call.get('args'), dict):
            raise RuntimeError('Chiamata Antigravity non valida o non autorizzata')
        calls.append({'id': 'agy-' + uuid.uuid4().hex, 'name': call['name'],
                      'args': call['args'], 'type': 'tool_call'})
    if not calls and not value['content'].strip():
        raise RuntimeError('Risposta Antigravity vuota')
    return {'content': value['content'], 'tool_calls': calls}
