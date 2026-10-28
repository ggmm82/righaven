"""Native Python engines for complementary capabilities, launched in isolated venvs."""
import hashlib
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
from urllib.parse import urlparse, unquote
import xml.etree.ElementTree as ET


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def local_reference(base, value):
    url = urlparse(value)
    if url.scheme not in ('', 'file') or url.netloc not in ('', 'localhost') or '\\' in value:
        raise ValueError('Media reference must be a local workspace file: '+value[:180])
    path = Path(unquote(url.path))
    path = path if path.is_absolute() else base / path
    root = Path(os.environ.get('RIGHAVEN_WORKSPACE_ROOT','/mnt/user-data')).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Media reference outside the workspace: '+value[:180])
    if not path.is_file(): raise ValueError('Missing media: '+value[:180])
    return path.resolve()


def timeline_info(timeline, source):
    import opentimelineio as otio
    issues=[];clips=[]
    for clip in timeline.find_clips():
        ref=clip.media_reference
        row={'name':clip.name,'duration_seconds':clip.duration().to_seconds()}
        if not math.isfinite(row['duration_seconds']) or row['duration_seconds'] <= 0:
            issues.append(clip.name+': invalid duration')
        if isinstance(ref,otio.schema.ExternalReference):
            row['reference']=ref.target_url
            try: row['resolved']=str(local_reference(source.parent,ref.target_url))
            except ValueError as error: issues.append(str(error))
            if clip.source_range and ref.available_range:
                wanted=clip.source_range;available=ref.available_range
                # OTIO contains(TimeRange) is strict; identical valid ranges return False.
                if (wanted.start_time.to_seconds()<available.start_time.to_seconds()-1e-9 or
                        wanted.end_time_exclusive().to_seconds()>available.end_time_exclusive().to_seconds()+1e-9):
                    issues.append(clip.name+': source range exceeds available media range')
        else: issues.append(clip.name+': no external media to verify')
        clips.append(row)
    if not clips: issues.append('Timeline contains no clips')
    return {'status':'failed' if issues else 'passed','name':timeline.name,
            'duration_seconds':timeline.duration().to_seconds(),
            'tracks':[{'name':t.name,'kind':str(getattr(t,'kind',''))} for t in timeline.tracks],
            'clips':clips,'issues':issues,
            'limits':'Timeline metadata and local files checked; no decoding, rendering or perceptual sync review.'}


def mesh_info(ms):
    if ms.mesh_number() < 1: raise ValueError('MeshLab project contains no meshes')
    mesh=ms.current_mesh()
    if mesh.vertex_number() < 1: raise ValueError('Mesh contains no vertices')
    return {'status':'passed','meshes':ms.mesh_number(),'vertices':mesh.vertex_number(),
            'faces':mesh.face_number(),'bounds':[mesh.bounding_box().min().tolist(),mesh.bounding_box().max().tolist()],
            'limits':'Native mesh geometry reopened; no parametric CAD history, rig or visual-quality certification.'}


def main():
    app,action,src,dest,params=sys.argv[1:]
    source=Path(src);output=Path(dest);args=json.loads(params)
    if action=='version':
        from importlib.metadata import version
        __import__(app)
        print(app+' '+version(app));return
    if action=='execute':
        __import__(app)
        os.environ['righaven_JOB_OUTPUT']=str(output)
        os.chdir(source.parent)
        runpy.run_path(str(source),run_name='__main__');return
    if app=='ifcopenshell':
        import ifcopenshell
        model=ifcopenshell.open(str(source))
        info={'status':'passed','schema':model.schema,'entities':len(list(model)),
              'projects':[{'name':p.Name,'global_id':p.GlobalId} for p in model.by_type('IfcProject')],
              'units':[[unit.get_info() for unit in assignment.Units] for assignment in model.by_type('IfcUnitAssignment')],
              'entity_counts':{kind:len(model.by_type(kind)) for kind in ('IfcSite','IfcBuilding','IfcBuildingStorey','IfcWall','IfcSlab','IfcDoor','IfcWindow')}}
        if not info['entities']:info.update(status='failed',issues=['IFC contains no entities'])
        if action=='check':
            import ifcopenshell.validate
            log=ifcopenshell.validate.json_logger()
            ifcopenshell.validate.validate(model,log)
            info['issues']=log.statements
            if any(s.get('level')=='error' for s in log.statements):info['status']='failed'
        write(output,info);return
    if app=='pymeshlab':
        import pymeshlab
        if action=='filters':write(output,{'filters':pymeshlab.filter_list(),'evidence':'registered, not all executed'});return
        try:from source_packages import mesh_dependencies
        except ImportError:from righaven.source_packages import mesh_dependencies
        dependencies=mesh_dependencies(source,Path(os.environ.get('RIGHAVEN_WORKSPACE_ROOT','/mnt/user-data')))
        ms=pymeshlab.MeshSet()
        if source.suffix.lower()=='.mlp':
            for node in ET.parse(source).findall('.//MLMesh'):
                local_reference(source.parent,node.attrib['filename'])
            ms.load_project(str(source))
        else:ms.load_new_mesh(str(source))
        if action=='apply':
            before=mesh_info(ms)
            if ms.mesh_number()!=1 or ms.current_mesh().texture_number():
                raise ValueError('apply supports one untextured mesh; use execute with explicit asset preservation for multi-mesh or textured projects')
            ms.load_filter_script(args['filters']);ms.apply_filter_script()
            ms.save_current_mesh(str(output/'mesh.ply'))
            ms.save_filter_script(str(output/'procedure.mlx'))
            ms.save_project(str(output/'project.mlp'))
            tree=ET.parse(output/'project.mlp')
            for node in tree.findall('.//MLMesh'):
                path=Path(node.attrib['filename'])
                if path.is_absolute():node.set('filename',path.resolve().relative_to(output.resolve()).as_posix())
            tree.write(output/'project.mlp',encoding='utf-8',xml_declaration=True)
            write(output/'inspection.json',{'before':before,'after':mesh_info(ms)})
        else:write(output,{**mesh_info(ms),'dependencies':[str(p) for p in dependencies]})
        return
    if app=='opentimelineio':
        import opentimelineio as otio
        timeline=otio.adapters.read_from_file(str(source))
        info=timeline_info(timeline,source)
        if action=='pack':
            if info['status']!='passed':raise ValueError('; '.join(info['issues']))
            clone=timeline.deepcopy()
            # Distinct files can have the same basename. Give the bundle stable,
            # content-addressed names instead of silently overwriting a clip.
            with tempfile.TemporaryDirectory(prefix='otio-media-',dir=output) as temp:
                stage=Path(temp)
                for clip in clone.find_clips():
                    ref=clip.media_reference;path=local_reference(source.parent,ref.target_url)
                    with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
                    target=stage/(sha[:20]+'-'+path.name)
                    if not target.exists():shutil.copy2(path,target)
                    ref.target_url=target.as_uri()
                otio.adapters.write_to_file(clone,str(output/'Timeline.otiod'),adapter_name='otiod')
            packed=output/'Timeline.otiod/content.otio'
            write(output/'inspection.json',timeline_info(otio.adapters.read_from_file(str(packed)),packed))
        else:write(output,info)
        return
    raise ValueError('Unknown native operation')


if __name__=='__main__':main()
