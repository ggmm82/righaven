"""Data-only validation shared by native design adapters and user revisions."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

APPS={'d2','plantuml','mermaid','excalidraw','bpmn','structurizr'}
EXTENSIONS={'d2':'.d2','plantuml':'.puml','mermaid':'.mmd','excalidraw':'.excalidraw','bpmn':'.bpmn','structurizr':'.dsl'}


def preflight(app,source):
    if source.stat().st_size>8*1024*1024:raise ValueError('Design source exceeds 8 MiB')
    text=source.read_text()
    if app=='structurizr' and re.search(r'(?im)^\s*!(?:include|script|plugin|docs|adrs)|\b(?:themes?|extends)\s+["\']?https?://',text):
        raise ValueError('Use a self-contained DSL without scripts, plugins or external includes')
    if app=='plantuml':
        for line in text.splitlines():
            if re.match(r'\s*!include',line,re.I) and not re.fullmatch(r'\s*!include\s+<C4/[A-Za-z0-9_./-]+>\s*',line):
                raise ValueError('Only the bundled C4 standard library may be included')
        if re.search(r'(?i)%load_json|%load_yaml|!import|!includeurl|!include_many|%getenv|%file_exists',text):raise ValueError('External data and environment reads are not part of a portable UML source')
    if app=='d2':
        if re.search(r'(?m)^\s*[^#\n]*:\s*@',text):raise ValueError('Use a single self-contained D2 source')
        for line in text.splitlines():
            match=re.match(r'\s*(?:[\w.-]+\.)?icon:\s*(.*)',line)
            if match and not match[1].strip().strip('"').startswith('data:'):
                raise ValueError('Use embedded D2 icons instead of external resources')
    if app=='excalidraw':
        value=json.loads(text)
        if not isinstance(value,dict):raise ValueError('Excalidraw document must be an object')
        if value.get('type')!='excalidraw' or not isinstance(value.get('elements'),list) or not value['elements'] or len(value['elements'])>5000:raise ValueError('Invalid or empty Excalidraw scene')
        if not isinstance(value.get('files',{}),dict):raise ValueError('Excalidraw image inventory must be an object')
        for image in (value.get('files') or {}).values():
            if not isinstance(image,dict) or not str(image.get('dataURL','')).startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,','data:image/svg+xml;base64,')):
                raise ValueError('Embed image resources in the Excalidraw document')
    if app=='bpmn':
        if '<!DOCTYPE' in text or '<!ENTITY' in text:raise ValueError('External XML entities are not supported')
        try:root=ET.fromstring(text)
        except ET.ParseError as error:raise ValueError('BPMN XML non valido') from error
        ids=[n.get('id') for n in root.iter() if n.get('id')]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate BPMN element IDs')
    return text

