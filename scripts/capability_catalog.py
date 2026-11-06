"""Read pinned native registries without treating registration as execution proof."""
import json
import re


def command_ids(text):
    try:
        value=json.loads(text)
    except ValueError:
        return sorted(set(re.findall(r'^([A-Za-z_][A-Za-z_0-9.:/-]*)\*?\s+',text,re.M)))
    if isinstance(value,dict):value=value.get('tools',value.get('commands',[]))
    if not isinstance(value,list):raise ValueError('Catalogo nativo non riconosciuto')
    return sorted({r.get('id') or r.get('name') for r in value if isinstance(r,dict) and isinstance(r.get('id') or r.get('name'),str)})
