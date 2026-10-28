"""Trace editable component sources, including media inside portable ZIPs.

An editable parent timeline does not establish editability of its ingredients.
This checks inventory/claims; it never executes a delivered regeneration script.
"""
from pathlib import Path, PurePosixPath
from contextlib import ExitStack
import hashlib
import zipfile
import stat

FLAT = {'.wav','.mp3','.m4a','.ogg','.flac','.aac','.mp4','.mov','.webm','.mkv','.png','.jpg','.jpeg','.webp'}
ASSETS = FLAT | {'.svg','.obj','.glb','.gltf'}
NATIVE_TOOL = {'.scraft':'soundcraft','.ecproj':'effectcraft','.fcproj':'filmcraft','.blend':'blender','.fcstd':'freecad','.mscz':'musescore','.ifc':'ifcopenshell','.otio':'opentimelineio','.mlp':'pymeshlab','.py':'manim','.d2':'d2','.puml':'plantuml','.mmd':'mermaid','.excalidraw':'excalidraw','.bpmn':'bpmn','.dsl':'structurizr'}


def component_metadata(component, index):
    """Same field limits in provider schema, local preflight and runtime."""
    prefix = f'delivery.components[{index}]'
    if not isinstance(component, dict):
        raise ValueError(prefix + ': oggetto obbligatorio')
    for field, maximum in (('name', 140), ('tool', 48)):
        value = component.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f'{prefix}.{field}: da 1 a {maximum} caratteri; usa un ID breve per tool, descrivi il metodo in name o nella guida')
    for field, maximum in (('artifacts', 64), ('sources', 24)):
        values = component.get(field)
        if not isinstance(values, list) or not 1 <= len(values) <= maximum:
            raise ValueError(f'{prefix}.{field}: da 1 a {maximum} riferimenti effettivi')
        for i, ref in enumerate(values):
            if (not isinstance(ref, dict) or set(ref) - {'path', 'member'}
                    or not isinstance(ref.get('path'), str) or not ref['path'].strip()
                    or 'member' in ref and (not isinstance(ref['member'], str) or not ref['member'].strip())):
                raise ValueError(f'{prefix}.{field}[{i}]: path e member opzionale, stringhe non vuote')


def inspect_components(handoff, files, *, required=False, workspace=None, inventory_only=False):
    declared = (handoff.get('delivery') or {}).get('components')
    if declared is None:
        return {'status':'not_recorded','components':[], 'issues':
                ['Mappa dei sorgenti delle componenti non registrata; il progetto principale non ne dimostra la modificabilità.'] if required else []}
    if not isinstance(declared,list) or not 1 <= len(declared) <= 12:
        return {'status':'incomplete','components':[],'issues':['Componenti: specificare da 1 a 12 componenti reali.']}
    downloaded={f['path']:f for f in files}
    indexes={}
    for path,item in downloaded.items():
        if item.get('role')=='source_archive' and (inventory_only or item.get('verification',{}).get('status')=='passed'):
            indexes[path]={}
            budget={'files':0,'bytes':0}
            def collect(archive,prefix='',parents=(),depth=0):
                for item in archive.infolist():
                    name = PurePosixPath(item.filename)
                    if name.is_absolute() or '..' in name.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                        raise ValueError('Inventario: membro ZIP non sicuro')
                    if item.is_dir():continue
                    budget['files']+=1;budget['bytes']+=item.file_size
                    if budget['files']>12000 or budget['bytes']>512*1024*1024:
                        raise ValueError('Inventario oltre il budget del pacchetto verificato')
                    name=prefix+item.filename
                    indexes[path][name]=(*parents,item.filename)
                    if PurePosixPath(item.filename).suffix.lower()=='.zip':
                        if depth>=2:raise ValueError('Archivi troppo annidati')
                        with archive.open(item) as stream, zipfile.ZipFile(stream) as nested:
                            collect(nested,name+'/',(*parents,item.filename),depth+1)
            with zipfile.ZipFile(path) as archive:collect(archive)
    def ref(value):
        if not isinstance(value,dict) or set(value)-{'path','member'} or value.get('path') not in downloaded:
            raise ValueError('riferimento non scaricabile')
        path=value['path'];member=value.get('member')
        if member is not None:
            if (not isinstance(member,str) or (member not in indexes.get(path,set())
                    and not (member.endswith('/') and any(n.startswith(member) for n in indexes.get(path,set()))))):
                raise ValueError('file non presente nel pacchetto verificato')
            return (path,member),member
        if Path(path).suffix.lower()=='.zip':
            raise ValueError('indicare il file interno allo ZIP, non soltanto l’archivio')
        return (path,''),path
    covered=set();result=[];issues=[]
    for index, component in enumerate(declared):
        try:
            component_metadata(component, index)
            name,tool=component.get('name'),component.get('tool')
            tool=tool.lower()
            artifacts,sources=component.get('artifacts'),component.get('sources')
            if not isinstance(artifacts,list) or not 1<=len(artifacts)<=64 or not isinstance(sources,list) or not 1<=len(sources)<=24:
                raise ValueError('artefatti e sorgenti effettivi obbligatori')
            artifact_refs=[ref(v) for v in artifacts];source_refs=[ref(v) for v in sources]
            source_names=[v[1] for v in source_refs]
            if any(n.endswith('/') for n in source_names):
                raise ValueError('indicare un sorgente effettivo, non soltanto una cartella')
            provided=component.get('provided_inputs',[])
            if provided:
                if not workspace or not isinstance(provided,list) or len(provided)>64:
                    raise ValueError('originali caricati non verificabili')
                hashes=set()
                for filename in provided:
                    p=Path(filename)
                    if filename not in handoff.get('source_files',[]) or not p.resolve().is_relative_to(Path(workspace).resolve()/'uploads'):
                        raise ValueError('originale non presente tra gli input caricati dall’utente')
                    with p.open('rb') as stream:hashes.add(hashlib.file_digest(stream,'sha256').hexdigest())
                for (path,member),_ in artifact_refs+source_refs:
                    if member:
                        with ExitStack() as opened:
                            archive=opened.enter_context(zipfile.ZipFile(path))
                            locator=indexes[path][member]
                            for part in locator[:-1]:
                                stream=opened.enter_context(archive.open(part))
                                archive=opened.enter_context(zipfile.ZipFile(stream))
                            stream=opened.enter_context(archive.open(locator[-1]))
                            value=hashlib.file_digest(stream,'sha256').hexdigest()
                    else:
                        with Path(path).open('rb') as stream:value=hashlib.file_digest(stream,'sha256').hexdigest()
                    if value not in hashes:raise ValueError('la componente non coincide con l’originale fornito')
            if not provided and not any(Path(n).suffix.lower() not in FLAT for n in source_names):
                raise ValueError('sono presenti solo file appiattiti; manca progetto o ricetta modificabile')
            expected=next((suffix for suffix,app in NATIVE_TOOL.items() if app==tool),None)
            if not provided and expected and not any(Path(n).suffix.lower()==expected for n in source_names):
                raise ValueError('manca il progetto '+expected+' dello strumento dichiarato')
            for (path,member),_ in artifact_refs:
                if member.endswith('/'):
                    covered.update((path,n) for n in indexes[path] if n.startswith(member))
                else:
                    covered.add((path,member))
            result.append({'name':name,'tool':tool,'status':'documented',
                           'sources':[{'path':r[0][0],**({'member':r[0][1]} if r[0][1] else {})} for r in source_refs]})
        except (ValueError,TypeError,KeyError) as error:
            label=component.get('name','Componente') if isinstance(component,dict) else 'Componente'
            issues.append(str(label)[:140]+': '+str(error))
            result.append({'name':str(label)[:140],'tool':str(component.get('tool',''))[:48] if isinstance(component,dict) else '',
                           'status':'incomplete','sources':[]})
    expected={(p,'') for p,f in downloaded.items() if f.get('role')=='export'
              or f.get('role')=='dependency' and Path(p).suffix.lower() in ASSETS}
    expected.update((p,n) for p,names in indexes.items() for n in names if PurePosixPath(n).suffix.lower() in ASSETS)
    # A portable package often repeats an already documented download. Carry
    # coverage only across byte-identical copies, never across names alone.
    hashes = {}
    def identity(location):
        if location not in hashes:
            path,member = location
            with ExitStack() as opened:
                if member:
                    archive=opened.enter_context(zipfile.ZipFile(path))
                    locator=indexes[path][member]
                    for part in locator[:-1]:
                        stream=opened.enter_context(archive.open(part))
                        archive=opened.enter_context(zipfile.ZipFile(stream))
                    stream=opened.enter_context(archive.open(locator[-1]))
                else:
                    stream=opened.enter_context(Path(path).open('rb'))
                hashes[location]=hashlib.file_digest(stream,'sha256').hexdigest()
        return hashes[location]
    named = {}
    for location in covered:
        named.setdefault(PurePosixPath(location[1] or location[0]).name, []).append(location)
    for location in expected-covered:
        candidates = named.get(PurePosixPath(location[1] or location[0]).name, [])
        if candidates and any(identity(location) == identity(other) for other in candidates):
            covered.add(location)
    missing=expected-covered
    if missing:
        issues.append('Componenti prive di sorgenti associati: '+', '.join(
            PurePosixPath(p).name + ':' + n if n else PurePosixPath(p).name for p,n in sorted(missing)[:6]))
    return {'status':'incomplete' if issues else 'documented','components':result,'issues':issues[:12],
            'notice':'Inventario dei sorgenti; non prova da solo che una ricetta rigeneri gli stessi risultati o che una GUI li apra.'}
