"""Trusted bpy entry point, invoked by blender_cli in the disposable sandbox."""
import json
from pathlib import Path
import runpy
import sys
import time
import os

import bpy


def inspect():
    scene = bpy.context.scene
    dependencies = []
    raw = bpy.utils.blend_paths(absolute=False, packed=False, local=False)
    absolute = bpy.utils.blend_paths(absolute=True, packed=False, local=False)
    for ref, resolved in zip(raw, absolute):
        path = Path(resolved).resolve()
        dependencies.append({'reference': ref, 'path': str(path), 'exists': path.is_file()})
    # Packed images do not make simulations or movie/image sequences portable.
    limitations = []
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.type in ('FLUID', 'CLOTH', 'SOFT_BODY', 'DYNAMIC_PAINT'):
                limitations.append(obj.name + ': ' + modifier.type + ' richiede verifica specifica di cache/dipendenze procedurali')
        if obj.particle_systems:
            limitations.append(obj.name + ': simulazione particellare da verificare')
    for group in bpy.data.node_groups:
        for node in group.nodes:
            kind = node.bl_idname
            if kind in ('GeometryNodeSimulationInput', 'GeometryNodeSimulationOutput', 'GeometryNodeBake') or kind.startswith('GeometryNodeImport'):
                limitations.append(group.name + ': ' + kind + ' richiede verifica specifica di cache/file esterni')
    for image in bpy.data.images:
        if image.source in ('SEQUENCE', 'MOVIE', 'TILED'):
            limitations.append(image.name + ': sequenza/video/UDIM richiede pacchetto e verifica specifici')
    return {'project': bpy.data.filepath, 'version': bpy.app.version_string,
            'objects': [{'name': o.name, 'type': o.type, 'modifiers': [m.type for m in o.modifiers],
                         'animated': bool(o.animation_data), 'vertices': len(o.data.vertices) if o.type == 'MESH' else None}
                        for o in bpy.data.objects],
            'materials': len(bpy.data.materials), 'images': len(bpy.data.images),
            'frame_start': scene.frame_start, 'frame_end': scene.frame_end,
            'fps': scene.render.fps / scene.render.fps_base,
            'resolution': [scene.render.resolution_x, scene.render.resolution_y],
            'dependencies': dependencies, 'limitations': limitations}


def main():
    job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text())
    if job.get('project'):
        bpy.ops.wm.open_mainfile(filepath=job['project'], load_ui=False, use_scripts=False)
    action = job['action']
    if action == 'execute':
        runpy.run_path(job['script'], run_name='__main__')
    elif action in ('render', 'profile'):
        scene = bpy.context.scene
        if job.get('frame') is not None:
            scene.frame_set(job['frame'])
        requested = [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage, scene.cycles.samples]
        requested_area = 1
        if scene.render.use_border:
            requested_area = (scene.render.border_max_x - scene.render.border_min_x) * (scene.render.border_max_y - scene.render.border_min_y)
        if action == 'profile':
            if scene.render.engine != 'CYCLES':
                raise ValueError('Profilazione automatica disponibile per Cycles CPU. Verificare gli altri motori separatamente con il supervisore.')
            width = max(1, scene.render.resolution_x * scene.render.resolution_percentage / 100)
            height = max(1, scene.render.resolution_y * scene.render.resolution_percentage / 100)
            scene.render.use_border = True
            scene.render.use_crop_to_border = True
            scene.render.border_min_x = max(0, .5 - 64 / width)
            scene.render.border_max_x = min(1, .5 + 64 / width)
            scene.render.border_min_y = max(0, .5 - 64 / height)
            scene.render.border_max_y = min(1, .5 + 64 / height)
            scene.cycles.samples = min(8, scene.cycles.samples)
        scene.render.filepath = job['output']
        scene.render.image_settings.file_format = 'PNG'
        if scene.render.engine == 'CYCLES':
            scene.cycles.device = 'CPU'
        scene.render.use_file_extension = True
        benchmark_start = time.monotonic()
        bpy.ops.render.render(write_still=True)
        render_seconds = time.monotonic() - benchmark_start
    elif action == 'export_glb':
        bpy.ops.export_scene.gltf(filepath=job['output'], export_format='GLB')
    elif action == 'pack':
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=job['output'])
    elif action != 'inspect':
        raise ValueError('Azione non supportata')
    result = inspect()
    if action == 'profile':
        image = bpy.data.images.load(job['output'])
        pixels = max(1, image.size[0] * image.size[1])
        total = requested[0] * requested[1] * (requested[2] / 100) ** 2 * requested_area
        result['profile'] = {'measured_seconds': render_seconds, 'measured_pixels': pixels,
                             'requested_resolution': requested[:3], 'requested_samples': requested[3],
                             'rough_estimate_seconds': round(render_seconds * total / pixels * requested[3] / max(1, scene.cycles.samples)),
                             'note': 'Stima indicativa da ritaglio campione, non una promessa di consegna. Il progetto salvato è invariato.'}
    if job.get('output'):
        output = Path(job['output'])
        if not output.is_file() or not output.stat().st_size:
            raise ValueError('Output Blender mancante o vuoto')
        result['output'] = str(output)
    target = Path(job['result'])
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(result))
    os.replace(temp, target)


if __name__ == '__main__':
    main()
