"""Supervised, file-based adapters; no new provider settings or always-on services."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET

APPS={'musescore','ifcopenshell','manim','opentimelineio','pymeshlab'}


def python(app, install):return install/'apps'/app/'venv/bin/python'


def version(app, install, here):
    if app=='musescore':
        argv=['xvfb-run','--auto-servernum',str(install/'apps/musescore/squashfs-root/AppRun'),'--version']
    else:argv=[str(python(app,install)),str(here/'production_job.py'),app,'version','-','-','{}']
    result=subprocess.run(argv,capture_output=True,text=True,timeout=90,check=True)
    print(result.stdout+result.stderr)


def sources(source, output, resource, cli):
    target=output/'Sources'
    if resource:
        base=cli.scoped(resource,directory=True)
        if not source.is_relative_to(base) or output.is_relative_to(base):
            raise ValueError('resource_dir must contain the script and must not contain the output')
        if any(p.is_symlink() for p in base.rglob('*')):raise ValueError('Source resources must not contain symlinks')
        shutil.copytree(base,target)
        return target/source.relative_to(base)
    target.mkdir();shutil.copy2(source,target/source.name);return target/source.name


def score_preflight(source):
    """Reject malformed score data before Qt can display an unattended import dialog."""
    suffix=source.suffix.lower()
    if suffix in ('.mid','.midi'):
        with source.open('rb') as stream:
            if stream.read(4)!=b'MThd':raise ValueError('Invalid MIDI header')
        return
    if suffix in ('.mscz','.mxl'):
        with zipfile.ZipFile(source) as archive:
            members=archive.infolist()
            if sum(i.file_size for i in members)>256*1024*1024:raise ValueError('Score archive expansion exceeds limit')
            for item in members:
                name=Path(item.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in item.filename:raise ValueError('Unsafe score archive member')
            candidates=[i for i in members if i.filename.lower().endswith('.mscx' if suffix=='.mscz' else ('.xml','.musicxml')) and not i.filename.startswith('META-INF/')]
            if not candidates:raise ValueError('Score archive contains no editable score')
            data=archive.read(candidates[0])
    else:
        if source.stat().st_size>64*1024*1024:raise ValueError('Score XML exceeds inspection limit')
        data=source.read_bytes()
    try:root=ET.fromstring(data)
    except ET.ParseError as error:raise ValueError('Malformed score XML') from error
    if root.tag.split('}')[-1] not in ('museScore','score-partwise','score-timewise'):
        raise ValueError('Unrecognized score XML')


def invoke(app,action,args,cli):
    source=cli.scoped(args['input']) if 'input' in args else None
    directory=action in ('execute','render','apply','pack')
    output=cli.scoped(args['output'],exists=False,directory=directory,fresh=True)
    if action in ('execute','render') and source.suffix.lower()!='.py':raise ValueError('An explicit Python source is required')
    if app=='ifcopenshell' and action!='execute' and source.suffix.lower()!='.ifc':raise ValueError('An IFC source is required')
    if app=='opentimelineio' and action!='execute' and source.suffix.lower()!='.otio':raise ValueError('Use an editable .otio timeline; extract a bundle before inspecting it')
    if app=='pymeshlab' and source and action not in ('execute',) and source.suffix.lower() not in ('.ply','.obj','.stl','.off','.mlp'):
        raise ValueError('Use PLY, OBJ, STL, OFF or an MLP project')
    if app=='musescore':
        if source.suffix.lower() not in ('.mscz','.mscx','.musicxml','.mxl','.xml','.mid','.midi'):raise ValueError('Use a native score, MusicXML or MIDI')
        allowed={'.json'} if action=='inspect' else {'.mscz','.mscx','.musicxml','.mxl','.mid','.midi','.pdf','.wav','.mp3'}
        if output.suffix.lower() not in allowed:raise ValueError('Unsupported score output format')
        score_preflight(source)
    elif not directory and output.suffix.lower()!='.json':raise ValueError('Inspection output must be JSON')
    if action=='render' and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',args['scene']):raise ValueError('Use an explicit Scene class name')
    extra=dict(args)
    if 'filters' in args:
        filters=cli.scoped(args['filters'])
        if filters.suffix.lower()!='.mlx':raise ValueError('A native MLX filter script is required')
        extra['filters']=str(filters)
    root=cli.scoped(os.environ.get('RIGHAVEN_OUTPUT_DIR',str(output.parent)),exists=False,directory=True)
    root.mkdir(parents=True,exist_ok=True);output.parent.mkdir(parents=True,exist_ok=True)
    if directory:output.mkdir()
    original=cli.digest(source) if source else None
    work=cli.folder(root,app+'-'+hashlib.sha256(str(output).encode()).hexdigest())
    actual=source
    if action in ('execute','render'):actual=sources(source,output,args.get('resource_dir'),cli)
    if app=='musescore':
        config=work/'config';config.mkdir(exist_ok=True)
        base=['/usr/bin/env','QT_QPA_PLATFORM=xcb','LIBGL_ALWAYS_SOFTWARE=1','XDG_CONFIG_HOME='+str(config),
              'xvfb-run','--auto-servernum',str(cli.INSTALL/'apps/musescore/squashfs-root/AppRun')]
        if action=='inspect':
            cli.capture(app,[*base,'--score-meta',str(source)],output,root)
            info=json.loads(output.read_text())
            if not isinstance(info,dict) or not info:raise ValueError('MuseScore returned no score metadata')
        else:
            job=work/'score-export.json';job.write_text(json.dumps([{'in':str(source),'out':str(output)}]))
            cli.run(app,[*base,'--sound-profile','MuseScore Basic','-j',str(job)],root)
    elif app=='manim':
        media=output/'Render';quality={'draft':'l','standard':'m','high':'h'}[args.get('quality','standard')]
        # CWD is explicit so relocated relative assets retain their meaning.
        argv=[str(cli.INSTALL/'apps/manim/venv/bin/manim'),'render','--renderer=cairo','-q'+quality,
              '--disable_caching','--media_dir',str(media),'--format=mp4',str(actual),args['scene']]
        runner=work/'render.json';runner.write_text(json.dumps({'argv':argv,'cwd':str(actual.parent)}))
        cli.run(app,[str(python(app,cli.INSTALL)),str(cli.HERE/'production_render.py'),str(runner)],root)
        videos=[p for p in media.rglob('*.mp4') if 'partial_movie_files' not in p.parts]
        if len(videos)!=1:raise ValueError('Manim did not create exactly one final scene video')
        (output/'render-recipe.json').write_text(json.dumps({'tool':'manim','scene':args['scene'],'quality':args.get('quality','standard'),
            'entrypoint':actual.relative_to(output).as_posix(),'source_sha256':cli.digest(actual)},indent=2))
    else:
        cli.run(app,[str(python(app,cli.INSTALL)),str(cli.HERE/'production_job.py'),app,action,
                    str(actual or '-'),str(output),json.dumps(extra)],root,env={'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
        if app=='pymeshlab' and action=='apply':
            try:from source_packages import mesh_dependencies
            except ImportError:from righaven.source_packages import mesh_dependencies
            dependencies=mesh_dependencies(source,cli.ROOT)
            base=Path(os.path.commonpath([str(source.parent),*[str(p.parent) for p in dependencies]]))
            retained=output/'Sources';retained.mkdir()
            for path in [source,*dependencies]:
                target=retained/path.relative_to(base);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            shutil.copy2(extra['filters'],retained/'input-procedure.mlx')
    if action=='execute':
        suffixes={'ifcopenshell':{'.ifc'},'opentimelineio':{'.otio'},'pymeshlab':{'.mlp','.ply','.obj','.stl','.off'}}[app]
        generated=[p for p in output.rglob('*') if p.is_file() and p.suffix.lower() in suffixes and not p.is_relative_to(output/'Sources')]
        if not generated:raise RuntimeError('Script produced no native document or geometry beyond captured sources')
    if not output.exists() or output.is_file() and not output.stat().st_size:raise RuntimeError('Native operation produced no output')
    if original and cli.digest(source)!=original:raise RuntimeError('Original input was modified')
    result={'output':str(output),'original_preserved':True}
    if not directory and output.suffix=='.json':
        info=json.loads(output.read_text());result['inspection']=info
        result['status']=info.get('status','passed')
    (work/'receipt.json').write_text(json.dumps({'app':app,'operation':action,'arguments':args,'input_sha256':original,'result':result},indent=2))
    return result
