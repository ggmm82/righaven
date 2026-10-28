"""Portable native sources: inspect actual references, relocate, then reopen.

No generated script from a delivery is executed. Only this trusted module and
the pinned CLIs run. The same standalone file prepares local paths after download.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import shlex
import xml.etree.ElementTree as ET
import stat
import subprocess
import tempfile
import zipfile

NATIVE = {'.fcproj', '.ecproj', '.scraft'}
DEPENDENT_PROJECTS = NATIVE | {'.otio', '.mlp'}
MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 12000
# Exact preparers published on main before the verifier gained more formats.
# They are never executed here: prepare() below is the trusted runtime code.
# Keep these identities when extending format checks, so existing sources reopen.
RELEASED_PREPARERS = {
    'da376510746c4d49c6ae905a87b49336dc158921c452cc5f3610e2b415ffb6c5',  # main before design tools: keep existing downloaded sources usable
    '12eabd2a5fef37534081cf20cf1b6eba22a9512caae9b857b1cce1d78024ea79',  # main before PR35: preserve existing downloaded sources
    '758746a8222abe6097be5d6a62cd61e1f9f3b14770362e4ec5e39d6940278a5b',  # PR30: keep downloaded source packages compatible
    'ca41c6293e01c00de24a64c0451fb31392e2f2e8ec9c8abd1e0d1a4e5dce2586',  # PR23 / 2de17e3
    'dc64bb7d149025adba6c380ab676d0d19bbb74ea0779f70e0e514dd1a8b4c73a',  # 6e19bcabb8
    '5cc17a70890beeb481d9782cb85ecf184b64b137e1eee02f440a16eb2ddf9ede',  # 0f7da4742f
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def references(value):
    """Yield mutable path slots from native documents, including footage frames.

Names are not paths. Embedded MIDI, geometries and shapes remain untouched.
Unknown external URI schemes fail closed rather than claiming offline portability.
"""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('path', 'file_path', 'filename') and isinstance(item, str) and item:
                yield value, key, item
            elif isinstance(item, (dict, list)):
                yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def document(path):
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Progetto troppo grande per la verifica: ' + path.name)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Documento nativo non valido: ' + path.name)
    if path.suffix == '.fcproj':
        if value.get('format') != 'filmcraft.project':
            raise ValueError('Formato FilmCraft non riconosciuto')
        sequences = [i['kind']['Sequence'] for i in value.get('project', {}).get('items', {}).values()
                     if 'Sequence' in i.get('kind', {})]
        if not any(t.get('items') for seq in sequences for k in ('video_tracks', 'audio_tracks') for t in seq.get(k, [])):
            raise ValueError('Timeline FilmCraft vuota: ' + path.name)
    elif path.suffix == '.ecproj':
        if not any(i.get('kind', {}).get('type') == 'Comp' and i['kind'].get('layers')
                   for i in value.get('items', {}).values()):
            raise ValueError('Composizione EffectCraft vuota: ' + path.name)
    elif path.suffix == '.scraft' and not value.get('tracks'):
        raise ValueError('Sessione SoundCraft vuota: ' + path.name)
    return value


def resolved_reference(project, ref, boundary, *, portable=False):
    path = Path(ref)
    if '\\' in ref or '://' in ref or (len(ref) > 1 and ref[1] == ':'):
        raise ValueError('Riferimento non portabile: ' + ref[:180])
    if portable and path.is_absolute():
        raise ValueError('Percorso assoluto nel pacchetto: ' + ref[:180])
    candidate = path if path.is_absolute() else project.parent / path
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(boundary.resolve()):
        raise ValueError('Dipendenza esterna al pacchetto/workspace: ' + ref[:180])
    if not candidate.is_file() or not candidate.stat().st_size:
        raise ValueError('Dipendenza mancante: ' + project.name + ' → ' + ref[:180])
    return candidate.resolve()


def extract(archive, destination, budget=None):
    """Bounded extraction; no links, traversal, duplicates or encrypted entries."""
    budget = budget if budget is not None else {'bytes': 0, 'files': 0}
    with zipfile.ZipFile(archive) as z:
        seen = set()
        for info in z.infolist():
            name = PurePosixPath(info.filename)
            if (name.is_absolute() or '..' in name.parts or '\\' in info.filename
                    or ':' in info.filename or not name.parts or name in seen
                    or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1):
                raise ValueError('Archivio non sicuro o ambiguo: ' + info.filename[:100])
            seen.add(name)
            budget['bytes'] += info.file_size
            budget['files'] += 1
            if budget['bytes'] > MAX_BYTES or budget['files'] > MAX_FILES:
                raise ValueError('Pacchetto oltre il budget di verifica (512 MiB / 12000 file)')
        z.extractall(destination)  # CRC checked by ZipFile while reading each file.


def prepare(folder):
    """Trusted local preparation, no app/install/network dependency.

FilmCraft 0.7.2 resolves relative media against process cwd. Generate adjacent
*.locale.fcproj copies with local absolute paths; originals stay portable.
"""
    folder = Path(folder).resolve()
    made = []
    for project in sorted(folder.rglob('*.fcproj')):
        if project.stem.endswith('.locale'):
            continue
        value = document(project)
        for owner, key, ref in references(value.get('project', {}).get('items', {})):
            owner[key] = str(resolved_reference(project, ref, folder, portable=True))
        target = project.with_name(project.stem + '.locale.fcproj')
        if target.is_symlink():
            raise ValueError('Destinazione locale non valida')
        target.write_text(json.dumps(value, ensure_ascii=False))
        made.append(target)
    return made


def run(argv, cwd, timeout=60):
    result = subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError('Riapertura nativa fallita: ' + Path(str(argv[0])).name + ' ' + result.stderr[-500:])
    return result.stdout


def sample(path, seconds=0):
    """Normalize decoded RGB before reduction, including PNG/YUV range differences."""
    result = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(seconds), '-i', str(path),
        '-frames:v', '1', '-vf', 'format=rgb24,scale=16:9:flags=area,format=rgb24', '-f', 'rawvideo', '-'],
        capture_output=True, timeout=30, check=True)
    if len(result.stdout) != 432:
        raise ValueError('Impossibile leggere il fotogramma: ' + Path(path).name)
    return list(result.stdout)


def inspect_blend(path, boundary, *, native=True):
    """Reopen using trusted code, then verify portable dependencies, not a claim."""
    if not native:
        return {'file': Path(path).name, 'status': 'not_run', 'check': 'blender_reopen'}
    result = subprocess.run(['blender-cli', 'inspect', str(path)], cwd=boundary,
        env={**os.environ, 'RIGHAVEN_WORKSPACE_ROOT': str(Path(boundary).resolve())},
        capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError('Blender: riapertura fallita: ' + result.stderr[-500:])
    info = json.loads(result.stdout)
    if not any(o.get('type') in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'VOLUME', 'POINTCLOUD', 'GREASEPENCIL')
               for o in info.get('objects', [])):
        raise ValueError('Blender: progetto senza geometria modificabile')
    if info.get('limitations'):
        raise ValueError('Blender: dipendenze non collaudate: ' + '; '.join(info['limitations'])[:700])
    for dependency in info.get('dependencies', []):
        ref = dependency['reference']
        if not ref.startswith('//') or not dependency['exists']:
            raise ValueError('Blender: risorsa mancante o percorso non portabile: ' + ref)
        actual = Path(dependency['path']).resolve()
        if not actual.is_relative_to(Path(boundary).resolve()):
            raise ValueError('Blender: dipendenza fuori dal pacchetto: ' + ref)
    return {'file': Path(path).relative_to(boundary).as_posix(), 'status': 'passed',
            'check': 'blender_reopen', 'objects': len(info['objects']),
            'dependencies': len(info.get('dependencies', [])),
            'note': 'CLI nativa, geometria e risorse; qualità artistica e GUI non certificate'}


def inspect_ebook(path, boundary, *, native=True):
    """Native content-container checks, independent of a project's domain or role."""
    if not native:
        return {'file': Path(path).name, 'status': 'not_run', 'check': 'calibre_structure'}
    boundary = Path(boundary).resolve()
    result = subprocess.run(['calibre-cli', 'check', str(path)], cwd=boundary,
        env={**os.environ, 'RIGHAVEN_WORKSPACE_ROOT': str(boundary), 'RIGHAVEN_OUTPUT_DIR': str(boundary)},
        capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ValueError('Calibre: controllo fallito: ' + (result.stderr or result.stdout)[-1200:])
    info = json.loads(result.stdout)
    if info.get('status') != 'passed' or not info.get('spine') or any(i.get('severity') == 'error' for i in info.get('issues', [])):
        raise ValueError('Calibre: struttura o risorse non valide')
    return {'file': Path(path).relative_to(boundary).as_posix(), 'status': 'passed',
            'check': 'calibre_structure', 'reading_order': len(info['spine']), 'resources': info.get('resources'),
            'warnings': info.get('issues', []), 'note': info.get('note', 'Controllo nativo; GUI e resa non provate')}


def inspect_freecad(path, boundary, *, native=True):
    """Actual native reopening; neither a STEP export nor a ZIP header is enough."""
    if not native:
        return {'file': Path(path).name, 'status': 'not_run', 'check': 'freecad_reopen'}
    boundary = Path(boundary).resolve()
    with tempfile.TemporaryDirectory(prefix='.freecad-proof-', dir=boundary) as temp:
        output = Path(temp) / 'inspection.json'
        result = subprocess.run(['freecad-cli', 'call', 'inspect', json.dumps({'input': str(path), 'output': str(output)})],
            cwd=boundary, env={**os.environ, 'RIGHAVEN_WORKSPACE_ROOT': str(boundary), 'RIGHAVEN_OUTPUT_DIR': temp},
            capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError('FreeCAD: riapertura fallita: ' + result.stderr[-1000:])
        info = json.loads(output.read_text())
    objects = info.get('objects', [])
    if not objects or any(o.get('invalid') or o.get('valid') is False for o in objects):
        raise ValueError('FreeCAD: documento vuoto, oggetti invalidi o solidi non validi')
    for reference in info.get('dependencies', []):
        ref = Path(reference)
        actual = (Path(path).parent / ref).resolve()
        if ref.is_absolute() or not actual.is_relative_to(boundary) or not actual.is_file():
            raise ValueError('FreeCAD: dipendenza mancante o non portabile: ' + reference)
    return {'file': Path(path).relative_to(boundary).as_posix(), 'status': 'passed', 'check': 'freecad_reopen',
            'objects': len(objects), 'dependencies': len(info.get('dependencies', [])),
            'note': 'Riapertura e geometria native; vincoli progettuali, GUI e conformità ingegneristica non certificate'}



def mesh_dependencies(source, boundary, *, portable=False):
    boundary=Path(boundary).resolve();seen=set();dependencies=[]
    def resolve(owner, reference):
        path=Path(reference)
        if ('\\' in reference or '://' in reference or ':' in reference or
                portable and path.is_absolute()):
            raise ValueError('Nonportable mesh resource: '+reference[:180])
        target=path if path.is_absolute() else owner.parent/path
        if target.is_symlink() or not target.resolve().is_relative_to(boundary):
            raise ValueError('Mesh resource outside allowed root: '+reference[:180])
        if not target.is_file() or not target.stat().st_size:
            raise ValueError('Missing mesh resource: '+reference[:180])
        target=target.resolve();dependencies.append(target)
        return target
    def visit(path,depth=0):
        if depth>4 or len(seen)>2048:raise ValueError('Mesh resource graph exceeds inspection limit')
        if path in seen:return
        seen.add(path)
        if path.suffix.lower()=='.mlp':
            try:nodes=ET.parse(path).findall('.//MLMesh')
            except ET.ParseError as error:raise ValueError('Malformed MeshLab project XML') from error
            for node in nodes:
                if not node.get('filename'):raise ValueError('MeshLab mesh reference missing')
                mesh=resolve(path,node.attrib['filename'])
                if mesh.suffix.lower() not in ('.obj','.ply','.stl','.off'):
                    raise ValueError('Mesh dependency format not verified by this adapter: '+mesh.suffix)
                visit(mesh,depth+1)
        elif path.suffix.lower() in ('.obj','.mtl','.ply'):
            with path.open('rb') as stream:
                for raw in stream:
                    if len(raw)>1024*1024:raise ValueError('Mesh metadata line exceeds inspection limit')
                    if path.suffix.lower()=='.ply' and raw.strip()==b'end_header':break
                    line=raw.decode('utf-8',errors='replace').strip()
                    if not line or line.startswith('#'):continue
                    parts=line.split(None,1);key=parts[0].lower();rest=parts[1].strip() if len(parts)>1 else ''
                    if key=='mtllib':
                        names=shlex.split(rest)
                        if (path.parent/rest).is_file():names=[rest]
                        for name in names:
                            material=resolve(path,name)
                            if material.suffix.lower()!='.mtl':raise ValueError('Normalize OBJ material files to .mtl before delivery')
                            visit(material,depth+1)
                    elif path.suffix.lower()=='.mtl' and (key.startswith('map_') or key in ('bump','disp','decal','refl','norm')):
                        if rest.startswith('-'):raise ValueError('Normalize MTL texture options before portable delivery: '+rest[:180])
                        names=shlex.split(rest);reference=names[0] if len(names)==1 else rest
                        resolve(path,reference)
                    elif path.suffix.lower()=='.ply' and line.lower().startswith('comment texturefile '):
                        resolve(path,line.split(None,2)[2])
    visit(Path(source).resolve())
    return sorted(set(dependencies))

# Data-only native formats. Never execute arbitrary Python found in a source ZIP.
PRODUCTION_NATIVE = {'.mscz': ('musescore', 'inspect'), '.mscx': ('musescore', 'inspect'),
                     '.ifc': ('ifcopenshell', 'check'), '.otio': ('opentimelineio', 'check'),
                     '.mlp': ('pymeshlab', 'inspect')}


def inspect_production(path, boundary, *, native=True):
    path=Path(path);boundary=Path(boundary).resolve()
    app,action=PRODUCTION_NATIVE[path.suffix.lower()]
    # Native loading must not hide absolute references which only work on the server.
    dependencies=[]
    if path.suffix.lower()=='.mlp':
        dependencies=[p.relative_to(path.parent).as_posix() if p.is_relative_to(path.parent) else os.path.relpath(p,path.parent)
                      for p in mesh_dependencies(path,boundary,portable=True)]
        if not dependencies:raise ValueError('MeshLab: progetto senza geometrie')
    elif path.suffix.lower()=='.otio':
        def collect(value):
            if isinstance(value,dict):
                if 'target_url' in value:dependencies.append(value['target_url'])
                for child in value.values():collect(child)
            elif isinstance(value,list):
                for child in value:collect(child)
        collect(json.loads(path.read_text()))
    for reference in dependencies:
        resolved_reference(path,reference,boundary,portable=True)
    if not native:
        return {'file':path.relative_to(boundary).as_posix(),'status':'not_run','check':app+'_reopen'}
    with tempfile.TemporaryDirectory(prefix='.'+app+'-proof-',dir=boundary) as temp:
        output=Path(temp)/'inspection.json'
        result=subprocess.run([app+'-cli','call',action,json.dumps({'input':str(path),'output':str(output)})],
            cwd=boundary,env={**os.environ,'RIGHAVEN_WORKSPACE_ROOT':str(boundary),'RIGHAVEN_OUTPUT_DIR':temp},
            capture_output=True,text=True,timeout=180)
        if result.returncode:raise ValueError(app+': controllo nativo fallito: '+(result.stderr or result.stdout)[-1000:])
        info=json.loads(output.read_text())
    if info.get('status','passed')!='passed':raise ValueError(app+': documento o risorse non validi')
    if app=='musescore' and not info.get('metadata',{}).get('measures'):
        raise ValueError('MuseScore: partitura vuota')
    if app=='ifcopenshell' and not info.get('entities'):
        raise ValueError('IfcOpenShell: documento IFC vuoto')
    return {'file':path.relative_to(boundary).as_posix(),'status':'passed','check':app+'_reopen',
            'dependencies':len(dependencies),'inspection':info,
            'note':'Documento dati riaperto con il runtime nativo; qualità percettiva e GUI non certificate'}


DESIGN_NATIVE={'.d2':'d2','.puml':'plantuml','.mmd':'mermaid','.excalidraw':'excalidraw','.bpmn':'bpmn','.dsl':'structurizr'}


def inspect_design(path,boundary,*,native=True):
    app=DESIGN_NATIVE[Path(path).suffix.lower()]
    if not native:return {'file':Path(path).relative_to(boundary).as_posix(),'status':'not_run','check':app+'_model'}
    with tempfile.TemporaryDirectory(prefix='.'+app+'-model-',dir=boundary) as temp:
        output=Path(temp)/'checked'
        action='validate' if app=='structurizr' else 'check'
        result=subprocess.run([app+'-cli','call',action,json.dumps({'input':str(path),'output':str(output)})],cwd=boundary,
            env={**os.environ,'RIGHAVEN_WORKSPACE_ROOT':str(Path(boundary).resolve()),'RIGHAVEN_OUTPUT_DIR':temp},capture_output=True,text=True,timeout=240)
        if result.returncode:raise ValueError(app+': modello non riapribile: '+(result.stderr or result.stdout)[-1200:])
        info=json.loads((output/'inspection.json').read_text())
        if info.get('status')!='passed':raise ValueError(app+': controllo nativo non superato')
    return {'file':Path(path).relative_to(boundary).as_posix(),'status':'passed','check':app+'_model',
            'inspection':info,'note':'Sorgente riaperto con parser/renderer nativo; correttezza progettuale da verificare'}


def inspect_tree(folder, *, native=False, budget=None, depth=0):
    folder = Path(folder).resolve()
    projects, checks = [], []
    for path in sorted(folder.rglob('*.blend')):
        checks.append(inspect_blend(path, folder, native=native))
    for path in sorted(list(folder.rglob('*'))):
        if path.suffix.lower() in DESIGN_NATIVE:
            checks.append(inspect_design(path,folder,native=native))
        if path.suffix.lower() in PRODUCTION_NATIVE:
            checks.append(inspect_production(path, folder, native=native))
        if path.suffix.lower() == '.fcstd':
            checks.append(inspect_freecad(path, folder, native=native))
        if path.suffix.lower() in ('.epub', '.azw3'):
            checks.append(inspect_ebook(path, folder, native=native))
        if path.suffix in NATIVE:
            value = document(path)
            scope = value.get('project', {}).get('items', {}) if path.suffix == '.fcproj' else value
            deps = [resolved_reference(path, ref, folder, portable=True) for _, _, ref in references(scope)]
            projects.append((path, value))
            checks.append({'file': path.relative_to(folder).as_posix(), 'dependencies': len(deps),
                           'status': 'passed', 'check': 'structure_and_dependencies'})
    # Nested archives are deliverables too: an intact top-level timeline does
    # not make a broken colleague source complete. Share extraction budget.
    for archive in sorted(folder.rglob('*.zip')):
        if depth >= 2:
            raise ValueError('Archivi troppo annidati: estrarre i sorgenti nel pacchetto')
        with tempfile.TemporaryDirectory(prefix='skill-nested-') as temp:
            extract(archive, Path(temp), budget)
            checks.extend({**c, 'file': archive.relative_to(folder).as_posix() + '/' + c['file']}
                          for c in inspect_tree(Path(temp), native=native, budget=budget, depth=depth+1))
    if native:
        # A different cwd reproduces the actual download/open failure.
        with tempfile.TemporaryDirectory(prefix='skill-unrelated-') as other:
            prepare(folder)
            for path, value in projects:
                if path.suffix == '.fcproj':
                    local = path.with_name(path.stem + '.locale.fcproj')
                    info = json.loads(run(['filmcraft-cli', '--project', local, 'inspect'], other))
                    media = json.loads(run(['filmcraft-cli', '--project', local, 'exec', 'media.status'], other))
                    if not info.get('sequence', {}).get('durationFrames') or any(m.get('status') != 'online' for m in media):
                        raise ValueError('FilmCraft: timeline vuota o media offline dopo il trasferimento')
                    duration = info['sequence']['duration'] / 254016000000
                    samples = []
                    for index, time in enumerate((0, duration * .5, max(0, duration - .1))):
                        frame = Path(other) / f'frame-{index}.png'
                        run(['filmcraft-cli', '--project', local, 'render', '--seconds', str(time),
                             '--out', str(frame), '--scale', '.25'], other)
                        samples.append({'seconds': time, 'luma': sample(frame)})
                    checks.append({'file': path.relative_to(folder).as_posix(), 'status': 'passed',
                        'check': 'filmcraft_render', 'duration': duration,
                        'width': info['sequence']['settings']['width'], 'height': info['sequence']['settings']['height'],
                        'sample_format': 'rgb24-area-v1', 'samples': samples})
                elif path.suffix == '.ecproj':
                    run(['effectcraft-cli', '--project', path, 'info'], path.parent)
                else:
                    run(['soundcraft-cli', 'run', '--in', path, '--inspect'], path.parent)
                checks.append({'file': path.relative_to(folder).as_posix(), 'status': 'passed',
                               'check': 'native_reopen', 'app': path.suffix,
                               'note': 'FilmCraft: preparazione locale, media online e tre frame renderizzati; GUI non provata'
                               if path.suffix == '.fcproj' else 'CLI nativa; GUI non provata'})
    return checks


def verify_archive(archive, *, native=False):
    with tempfile.TemporaryDirectory(prefix='skill-relocated-') as temp:
        folder = Path(temp)
        budget = {'bytes': 0, 'files': 0}
        extract(archive, folder, budget)
        checks = inspect_tree(folder, native=native, budget=budget)
        status = 'passed' if all(c['status'] == 'passed' for c in checks) else 'not_run'
        if any(c['file'].endswith('.fcproj') for c in checks):
            helper = folder / 'PREPARA_SORGENTI.py'
            # Do not execute an untrusted generated helper, even if named alike.
            if not helper.is_file() or digest(helper) not in {digest(__file__), *RELEASED_PREPARERS}:
                raise ValueError('FilmCraft richiede il pacchetto preparato con source_packages.py pack: '
                                 'percorsi relativi da soli non sono riapribili da altre cartelle')
        return {'status': status, 'sha256': digest(archive), 'files': budget['files'], 'checks': checks,
                'coverage': 'CRC e inventario; dipendenze/struttura FilmCraft, EffectCraft, SoundCraft; '
                            'Blender: riapertura, geometria e dipendenze se native=True; '
                            'Calibre: struttura e risorse EPUB/AZW3 se native=True; '
                            'FreeCAD: riapertura, oggetti e geometria .FCStd se native=True; '
                            'MuseScore/IFC/OTIO/MLP: riapertura e riferimenti supportati se native=True; '
                            'altri formati e scene Python richiedono la prova specifica della skill'}


def pack(project, destination, workspace):
    """Collect exact references; never guess a file by name or flatten sources."""
    project, destination, workspace = Path(project).resolve(), Path(destination).resolve(), Path(workspace).resolve()
    if project.suffix not in NATIVE or not project.is_relative_to(workspace) or not destination.is_relative_to(workspace):
        raise ValueError('Progetto o destinazione fuori dal workspace/formato supportato')
    value = document(project)
    scope = value.get('project', {}).get('items', {}) if project.suffix == '.fcproj' else value
    with tempfile.TemporaryDirectory(prefix='skill-pack-') as temp:
        folder = Path(temp)
        (folder / 'Media').mkdir()
        total, count = 0, 0
        for owner, key, ref in references(scope):
            source = resolved_reference(project, ref, workspace)
            total += source.stat().st_size
            count += 1
            if total > MAX_BYTES or count > MAX_FILES:
                raise ValueError('Dipendenze oltre il budget: suddividere il pacchetto')
            name = digest(source)[:16] + '-' + source.name
            shutil.copyfile(source, folder / 'Media' / name)
            owner[key] = 'Media/' + name
        (folder / project.name).write_text(json.dumps(value, ensure_ascii=False))
        shutil.copyfile(__file__, folder / 'PREPARA_SORGENTI.py')
        (folder / 'LEGGIMI.txt').write_text(
            'Estrarre TUTTO lo ZIP in una cartella. Non spostare il progetto da solo.\n'
            'FilmCraft 0.7.2: eseguire PREPARA_SORGENTI.py con Python 3, poi aprire il file .locale.fcproj '
            'generato, dalla app desktop FilmCraft compatibile con schema 15.\n'
            'Comando: python3 PREPARA_SORGENTI.py prepare .\n'
            'Windows: py PREPARA_SORGENTI.py prepare .\n'
            'La preparazione è offline, non installa software e non modifica gli originali. '
            'Se sposti la cartella, ripetila. In alternativa usa File > Link Media in FilmCraft '
            'e seleziona i media nella cartella Media.\n'
            'EffectCraft/SoundCraft: aprire il progetto con le risorse accanto. '
            'La verifica CLI non certifica app web o versioni GUI diverse.\n')
        (folder / 'CONTENUTO.json').write_text(json.dumps({'project': project.name,
            'files': [{'path': p.relative_to(folder).as_posix(), 'size': p.stat().st_size, 'sha256': digest(p)}
                      for p in sorted(folder.rglob('*')) if p.is_file()]}, ensure_ascii=False, indent=2))
        destination.parent.mkdir(parents=True, exist_ok=True)
        tempzip = destination.with_suffix('.partial')
        try:
            with zipfile.ZipFile(tempzip, 'w', zipfile.ZIP_DEFLATED) as z:
                for path in sorted(folder.rglob('*')):
                    if path.is_file():
                        z.write(path, path.relative_to(folder))
            verify_archive(tempzip, native=True)
            os.replace(tempzip, destination)
        finally:
            tempzip.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action')
    p = subs.add_parser('prepare'); p.add_argument('folder', nargs='?', default=str(Path(__file__).parent))
    p = subs.add_parser('verify'); p.add_argument('archive'); p.add_argument('--native', action='store_true')
    p = subs.add_parser('pack'); p.add_argument('project'); p.add_argument('destination'); p.add_argument('--workspace', default='/mnt/user-data')
    args = parser.parse_args()
    if args.action == 'pack':
        print(pack(args.project, args.destination, args.workspace))
    elif args.action == 'verify':
        print(json.dumps(verify_archive(args.archive, native=args.native), ensure_ascii=False))
    else:
        folder = getattr(args, 'folder', str(Path(__file__).parent))
        print('Apri questi progetti locali:', *prepare(folder), sep='\n')


if __name__ == '__main__':
    main()
