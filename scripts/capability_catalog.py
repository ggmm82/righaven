"""Read pinned native registries without treating registration as execution proof."""
import json
import re


def command_ids(text, registry_format=None):
    if registry_format == 'help-commands':
        # Clap prints an indented Commands section. Typer wraps the same
        # information in a Rich table with a box around its command rows.
        rich = re.search(r'^╭─+ Commands ─+╮\s*$([\s\S]*?)^╰─+╯', text, re.M)
        if rich:
            return sorted(set(re.findall(r'^│\s+([a-z][a-z0-9-]*)\s+', rich[1], re.M)))
        sections = re.findall(
            r'^(?:Commands|Main commands|All other commands):[ \t]*\n((?:[ \t]+[^\n]+\n?)+)',
            text,
            re.M,
        )
        return sorted(set(re.findall(r'^[ \t]+([a-z][a-z0-9-]*)[ \t]+', '\n'.join(sections), re.M)))

    try:
        value=json.loads(text)
    except ValueError:
        return sorted(set(re.findall(r'^([A-Za-z_][A-Za-z_0-9.:/-]*)\*?\s+',text,re.M)))
    if isinstance(value,dict):value=value.get('tools',value.get('commands',[]))
    if not isinstance(value,list):raise ValueError('Catalogo nativo non riconosciuto')
    return sorted({r.get('id') or r.get('name') for r in value if isinstance(r,dict) and isinstance(r.get('id') or r.get('name'),str)})
