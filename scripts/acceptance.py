#!/usr/bin/env python3
"""Real, deterministic file workflows for each RigHaven CLI. No model or account."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import uuid
import wave
import xml.etree.ElementTree as ET
import zipfile
import zlib

MARKER = 'righaven-COLLAUDO-60'


class Case:
    def __init__(self, root, app):
        self.app = app
        self.root = root / app / uuid.uuid4().hex[:8]
        self.root.mkdir(parents=True, exist_ok=True)
        self.commands = []
        self.checks = []

    def run(self, *args, timeout=180):
        args = [str(x) for x in args]
        result = subprocess.run(args, cwd=self.root, capture_output=True, text=True,
                                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}, timeout=timeout)
        self.commands.append({'argv': args, 'returncode': result.returncode,
                              'stdout': result.stdout[-12000:], 'stderr': result.stderr[-3000:]})
        if result.returncode:
            raise RuntimeError('Comando fallito: ' + ' '.join(args) + '\n' + (result.stderr or result.stdout)[-1000:])
        return result.stdout

    def check(self, name, condition, evidence):
        self.checks.append({'name': name, 'status': 'passed' if condition else 'failed', 'evidence': evidence})
        if not condition:
            raise AssertionError(name + ': ' + str(evidence))

    def batch(self, steps, name='sequence'):
        script = self.root / (name + '.json')
        script.write_text(json.dumps(steps, indent=2))
        output = self.root / (name + '-result.json')
        self.run('craft', 'batch', self.app, script, '--out', output)
        return json.loads(output.read_text())

    def probe(self, file):
        if Path(file).suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
            from PIL import Image
            with Image.open(file) as picture:
                return {'verification_engine':'Pillow','streams':[{'codec_type':'video','codec_name':picture.format.lower(), 'width':picture.width,'height':picture.height}]}
        return json.loads(self.run('ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', file))

    def pixels(self, file, time=None):
        if time is None and Path(file).suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
            from PIL import Image
            with Image.open(file) as picture:
                return picture.convert('RGBA').tobytes()
        seek = ['-ss', str(time)] if time is not None else []
        result = subprocess.run(['ffmpeg', '-v', 'error', *seek, '-i', str(file), '-frames:v', '1',
            '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError('Decodifica immagine fallita')
        return result.stdout


def step(tool, **arguments):
    return {'name': tool, 'arguments': arguments}


def png(path, width=64, height=48):
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    pixels = b''.join(b'\x00' + b''.join(bytes((x * 3, y * 4, 80, 0 if x < 8 else 255))
                    for x in range(width)) for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def make_pdf(case, name, marker=MARKER):
    source = case.root / (name + '.md')
    source.write_text('# Collaudo\n\n' + marker + '\n\nTotale verificato: 60.\n')
    target = case.root / (name + '.pdf')
    case.run('wordcraft-cli', 'convert', source, target)
    return target


def photocraft(c):
    source, native, output = [c.root / name for name in ('input.png', 'progetto.pcraft', 'output.png')]
    png(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    c.run('photocraft-cli', 'convert', source, native)
    info = c.run('photocraft-cli', 'info', native)
    c.run('photocraft-cli', 'convert', native, output)
    pixels = c.pixels(output)
    c.check('Dimensioni e alpha dopo riapertura del sorgente', len(pixels) == 64 * 48 * 4
            and pixels[3] == 0 and pixels[(20 * 64 + 20) * 4 + 3] == 255, info)
    c.check('Originale intatto', before == hashlib.sha256(source.read_bytes()).hexdigest(), before)


def vectorcraft(c):
    source, native, output, preview = [c.root / name for name in ('input.svg', 'logo.vectorcraft', 'logo.svg', 'preview.png')]
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="90" viewBox="0 0 160 90">'
        '<rect x="10" y="10" width="80" height="40" fill="#3366cc"/>'
        '<text x="10" y="75" font-family="DejaVu Sans" font-size="12">' + MARKER + '</text></svg>')
    c.run('vectorcraft-cli', 'convert', source, native)
    info = c.run('vectorcraft-cli', 'info', native)
    c.run('vectorcraft-cli', 'convert', native, output)
    c.run('vectorcraft-cli', 'convert', native, preview)
    tree = ET.parse(output)
    c.check('Testo vettoriale modificabile conservato', MARKER in ''.join(tree.getroot().itertext())
            and bool(tree.findall('.//{http://www.w3.org/2000/svg}text')), info)
    c.check('ViewBox conservato', tree.getroot().attrib.get('viewBox') == '0 0 160 90', tree.getroot().attrib)
    c.check('Anteprima decodificabile', len(c.pixels(preview)) > 0, str(preview))


def gridcraft(c):
    output = c.root / 'totali.xlsx'
    c.batch([step('new_workbook'), step('set_cell', cell='A1', input=10),
        step('set_cell', cell='A2', input=20), step('set_cell', cell='A3', input=30),
        step('set_cell', cell='A4', input='=SUM(A1:A3)'), step('save_workbook', path=str(output))])
    c.run('gridcraft-cli', 'check', output, '--json')
    with zipfile.ZipFile(output) as archive:
        tree = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    cells = {cell.attrib['r']: cell for cell in tree.findall('.//s:c', ns)}
    c.check('Formula e valore memorizzato indipendenti', cells['A4'].find('s:f', ns).text == 'SUM(A1:A3)'
        and float(cells['A4'].find('s:v', ns).text) == sum((10, 20, 30)), str(output))


def wordcraft(c):
    source, native, output = [c.root / name for name in ('input.md', 'relazione.docx', 'relazione.pdf')]
    source.write_text('# ' + MARKER + '\n\n| Voce | Totale |\n| --- | ---: |\n| Vendite | 60 |\n')
    c.run('wordcraft-cli', 'convert', source, native)
    c.run('wordcraft-cli', 'inspect', native)
    c.run('wordcraft-cli', 'convert', native, output)
    with zipfile.ZipFile(native) as archive:
        tree = ET.fromstring(archive.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    text = ''.join(node.text or '' for node in tree.findall('.//w:t', ns))
    c.check('Titolo, tabella e totale nel DOCX', MARKER in text and '60' in text
            and len(tree.findall('.//w:tbl', ns)) == 1, text)
    text = c.run('pdfcraft-cli', 'text', output)
    c.check('Contenuto del PDF riaperto', MARKER in text and '60' in text, text)


def pdfcraft(c):
    first = make_pdf(c, 'prima', MARKER + '-PRIMA')
    second = make_pdf(c, 'seconda', MARKER + '-SECONDA')
    output = c.root / 'unito.pdf'
    c.run('pdfcraft-cli', 'combine', first, second, '--out', output)
    info = c.run('pdfcraft-cli', 'info', output)
    text = c.run('pdfcraft-cli', 'text', output)
    c.check('Ordine e contenuto delle due pagine', text.index(MARKER + '-PRIMA') < text.index(MARKER + '-SECONDA'), info)
    c.check('Due pagine dopo unione', json.loads(info)['pages'] == 2, info)


def lightcraft(c):
    source, output = c.root / 'input.png', c.root / 'sviluppata.png'
    png(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    c.run('lightcraft-cli', 'render', source, '-o', output, '--set', 'light.exposure=0.5', '--size', '32')
    stream = c.probe(output)['streams'][0]
    c.check('Sviluppo ed export alle dimensioni richieste', stream['width'] == 32 and stream['height'] == 24, stream)
    c.check('Originale intatto', before == hashlib.sha256(source.read_bytes()).hexdigest(), before)
    raw_dir = c.root / 'raw'
    c.run('lightcraft-cli', 'synth-merge', 'hdr', '-o', raw_dir)
    raw = sorted(raw_dir.glob('*.dng'))[0]
    checksum = hashlib.sha256(raw.read_bytes()).hexdigest()
    raw_output = c.root / 'raw-sviluppato.png'
    c.run('lightcraft-cli', 'render', raw, '-o', raw_output, '--set', 'light.exposure=0.5', '--size', '64')
    metadata = c.probe(raw_output)['streams'][0]
    c.check('Sviluppo di un vero DNG sintetico', max(metadata['width'], metadata['height']) == 64
            and checksum == hashlib.sha256(raw.read_bytes()).hexdigest(), metadata)


def cadcraft(c):
    output, preview = c.root / 'rettangolo.dxf', c.root / 'rettangolo.svg'
    c.run('cadcraft-cli', 'run', '--metric', '--cmd', 'units {"insunits":4}', '--cmd',
        'pline {"vertices":[[0,0],[40,0],[40,20],[0,20]],"closed":true}', '--save', output)
    info = c.run('cadcraft-cli', 'info', output)
    c.run('cadcraft-cli', 'convert', output, preview)
    lines = output.read_text().splitlines()
    pairs = [(int(lines[i].strip()), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    start = pairs.index((0, 'LWPOLYLINE'))
    end = next((i for i in range(start + 1, len(pairs)) if pairs[i][0] == 0), len(pairs))
    entity = pairs[start + 1:end]
    xs = [float(v) for k, v in entity if k == 10]
    ys = [float(v) for k, v in entity if k == 20]
    unit = next(i for i, pair in enumerate(pairs) if pair == (9, '$INSUNITS'))
    c.check('DXF: geometria 40×20 mm e contorno chiuso, letti indipendentemente',
            len(xs) == len(ys) == 4 and max(xs) - min(xs) == 40 and max(ys) - min(ys) == 20
            and any(k == 70 and int(v) & 1 for k, v in entity) and int(pairs[unit + 1][1]) == 4, info)
    c.check('SVG valido', ET.parse(preview).getroot().tag.endswith('svg'), str(preview))
    edited = c.root / 'rettangolo-modificato.dxf'
    c.run('cadcraft-cli', 'run', output, '--cmd',
          'pline {"vertices":[[50,0],[60,0],[60,10]],"closed":true}', '--save', edited)
    reopened = c.run('cadcraft-cli', 'info', edited)
    c.check('Sorgente riaperto e modificabile in una nuova sessione CADCraft',
            edited.read_text().count('LWPOLYLINE') == 2, reopened)


def deckcraft(c):
    output, native, preview = c.root / 'slide.pptx', c.root / 'slide.deckcraft', c.root / 'slide.png'
    c.batch([step('new_presentation', blank=True), step('add_slide', layout='blank'),
        step('add_text_box', x=30, y=30, w=500, h=80, text=MARKER, size=28),
        step('save_presentation', path=str(native)), step('export', path=str(output), format='pptx')])
    c.run('deckcraft-cli', 'info', output)
    c.run('deckcraft-cli', 'render', output, '--slide', '0', preview)
    with zipfile.ZipFile(output) as archive:
        tree = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
    ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    c.check('Testo modificabile nel PPTX', MARKER in ''.join(n.text or '' for n in tree.findall('.//a:t', ns)), str(output))
    c.check('Slide riaperta e renderizzata', len(c.pixels(preview)) > 0, str(preview))


def filmcraft(c):
    source, native, output = c.root / 'clip.mp4', c.root / 'montaggio.fcproj', c.root / 'montaggio.mp4'
    second = c.root / 'seconda.mp4'
    for file, picture in ((source, 'testsrc2=size=160x90:rate=25'), (second, 'color=blue:size=160x90:rate=25')):
        c.run('ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', picture,
              '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
              '-t', '0.6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', file)
    c.batch([step('command_run', id='file.newProject', params={'name': MARKER}),
        step('media_import', paths=[str(source), str(second)]),
        step('command_run', id='file.newSequence', params={'name': 'Main',
             'fromItems': {'$result': '1.content.0.text.$json.items'}, 'width': 160, 'height': 90, 'fps': 25}),
        step('command_run', id='file.saveAs', params={'path': str(native)})])
    c.run('filmcraft-cli', '--project', native, 'inspect')
    c.run('filmcraft-cli', '--project', native, 'export', output, '--gpu-rendering', 'off')
    streams = c.probe(output)['streams']
    stream = next(s for s in streams if s['codec_type'] == 'video')
    c.check('Montaggio riaperto: dimensioni, fps e durata', stream['width'] == 160 and stream['height'] == 90
            and stream['r_frame_rate'] == '25/1' and abs(float(stream['duration']) - 1.2) < .08, stream)
    audio = next(s for s in streams if s['codec_type'] == 'audio')
    c.check('Audio presente e durata coerente con il video', int(audio['sample_rate']) == 48000
            and abs(float(audio['duration']) - float(stream['duration'])) < .08, audio)
    first, last = c.pixels(output, .1), c.pixels(output, 1.0)
    c.check('I due segmenti contengono immagini diverse', len(first) == len(last) == 160 * 90 * 4
            and first != last and sum(last[2::4]) > 2 * sum(last[0::4]), 'Frame decodificati a 0,1 e 1,0 secondi')


def effectcraft(c):
    native, first, last, output = [c.root / name for name in ('animazione.ecproj', 'prima.png', 'ultima.png', 'animazione.gif')]
    code = ('var c=app.project.items.addComp("Main",160,90,1,0.6,10);'
            'var l=c.layers.addSolid([0.2,0.5,1],"Box",30,30,1);'
            'l.property("Transform").property("Position").setValueAtTime(0,[30,45]);'
            'l.property("Transform").property("Position").setValueAtTime(0.5,[120,45]);')
    c.run('effectcraft-cli', '--empty', '--save-as', native, 'script', '--eval', code)
    c.run('effectcraft-cli', '--project', native, 'info')
    for time, file in ((0, first), (.5, last)):
        c.run('effectcraft-cli', '--project', native, 'render-frame', '--comp', 'Main', '--time', time,
              '--out', file, '--transparent')
    c.run('effectcraft-cli', '--project', native, 'render', '--comp', 'Main', '--out', output,
          '--format', 'gif', '--start', '0', '--end', '0.6', '--fps', '10')
    a, b = c.pixels(first), c.pixels(last)
    c.check('Keyframe persistenti e alpha', a != b and len(a) == len(b) == 160 * 90 * 4 and a[3] == 0, str(native))
    stream = c.probe(output)['streams'][0]
    c.check('GIF animata con sei fotogrammi', int(stream['nb_frames']) == 6, stream)
    # Fresh-process revisions must explicitly save; otherwise a successful set
    # can leave the original unchanged and waste an entire render/review cycle.
    changed = c.root / 'revision.png'
    c.run('effectcraft-cli', '--project', native, '--save', 'script', '--eval',
          'app.project.item(1).layer(1).property("Transform").property("Opacity").setValue(0);')
    c.run('effectcraft-cli', '--project', native, 'render-frame', '--comp', 'Main', '--time', '0',
          '--out', changed, '--transparent')
    pixels = c.pixels(changed)
    c.check('Revisione salvata e riaperta in processo nuovo', pixels != a and not any(pixels[3::4]), str(native))


def designcraft(c):
    native, output, preview = c.root / 'brochure.designcraft', c.root / 'brochure.pdf', c.root / 'pagina.png'
    c.run('designcraft-cli', 'run', '--cmd', 'file.new=' + json.dumps({'width': 360, 'height': 240, 'pages': 1, 'facingPages': False}),
          '--cmd', 'frame.create=' + json.dumps({'rect': [20, 20, 330, 120], 'content': 'text', 'text': MARKER}),
          '--cmd', 'file.saveAs=' + json.dumps({'path': str(native)}), '--export', output)
    text = c.run('pdfcraft-cli', 'text', output)
    c.check('Testo nell’export PDF', MARKER in text, text)
    c.run('designcraft-cli', 'run', '--in', native, '--export', preview)
    c.check('Sorgente editoriale riaperto e renderizzato', len(c.pixels(preview)) > 0, str(preview))
    preflight = json.loads(c.run('designcraft-cli', 'run', '--in', native, '--cmd', 'preflight.run={}'))
    c.check('Preflight editoriale senza errori', preflight['errors'] == 0, preflight)
    info = json.loads(c.run('pdfcraft-cli', 'info', output))
    c.check('Formato pagina e conteggio richiesti', info['pages'] == 1 and info['first_page_pt'] == [360, 240], info)


def soundcraft(c):
    source, native, output = c.root / 'sorgente.wav', c.root / 'sessione.scraft', c.root / 'mix.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
        wav.writeframes(b''.join(struct.pack('<h', int(6500 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(24000)))
    c.batch([step('new_session', name=MARKER, template='blank', sample_rate=48000),
        step('import_audio', path=str(source)), step('save_session', path=str(native)),
        step('bounce_mix', path=str(output), start=0, end=24000, bit_depth='16', format='wav')])
    c.run('soundcraft-cli', 'run', '--in', native, '--inspect')
    c.check('Dipendenze audio presenti nella consegna', (c.root / 'Audio Files/sorgente.wav').is_file(), str(native))
    with wave.open(str(output), 'rb') as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        duration = wav.getnframes() / rate
        data = wav.readframes(wav.getnframes())
    values = struct.unpack('<' + 'h' * (len(data) // 2), data)
    peak = max(abs(value) for value in values) / 32768
    c.check('Mix WAV: durata, canali, frequenza, bit depth e picco', rate == 48000 and channels == 2
            and width == 2 and abs(duration - .5) < .025 and .01 < peak < .5,
            {'rate': rate, 'channels': channels, 'bytes_per_sample': width, 'duration': duration, 'peak': peak})


def figcraft(c):
    native, output = c.root / 'interfaccia.figcraft', c.root / 'interfaccia.png'
    c.batch([step('run_command', command='file.new'),
        step('create_node', type='frame', name='Panel', width=320, height=180, props={'fill': '#ffffff'}),
        step('create_node', type='text', name='Status', text=MARKER,
             parent={'$result': '1.content.0.text.$json.id'}, x=20, y=20, width=280),
        step('save_file', path=str(native)), step('export', path=str(output),
             ids=[{'$result': '1.content.0.text.$json.id'}], format='png')])
    info = c.run('figcraft-cli', 'info', native, '--json')
    reopened = c.batch([step('open_file', path=str(native)), step('inspect_document', allPages=True)], 'reopen')
    c.check('Frame e testo nel sorgente riaperto', 'Panel' in info and MARKER in json.dumps(reopened), info)
    stream = c.probe(output)['streams'][0]
    c.check('Viewport richiesto', stream['width'] == 320 and stream['height'] == 180, stream)



def blender(c):
    script = c.root / 'create.py'
    native, packed, preview, glb = [c.root / n for n in ('scene.blend', 'delivery.blend', 'preview.png', 'scene.glb')]
    texture = c.root / 'texture.png'; png(texture)
    script.write_text("""import bpy, math
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
body=bpy.context.object; body.name='EditableBody';body.scale=(.5,.4,1)
mat=bpy.data.materials.new('PBR');mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image=bpy.data.images.load(TEXTURE);tex.image.pack()
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
body.data.materials.append(mat)
body.location=(0,0,1);body.keyframe_insert(data_path='location',frame=1)
body.location=(.5,0,1);body.keyframe_insert(data_path='location',frame=12)
bpy.ops.object.camera_add(location=(4,-6,3))
cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera=cam
bpy.ops.object.light_add(type='AREA',location=(2,-3,5))
bpy.context.object.data.energy=500;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=4
scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=12;scene.render.fps=24
scene.render.resolution_x=64;scene.render.resolution_y=64;scene.render.resolution_percentage=100
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=NATIVE)
""".replace('TEXTURE', repr(str(texture))).replace('NATIVE', repr(str(native))))
    c.run('blender-cli', 'execute', script)
    c.batch([step('blender.inspect', project=str(native)),
             step('blender.pack', project=str(native), output=str(packed))], name='native-mcp')
    info = json.loads(c.run('blender-cli', 'inspect', packed))
    c.check('Mesh, keyframe e materiale riaperti', any(o['name'] == 'EditableBody' and o['vertices'] == 8 and o['animated']
            for o in info['objects']) and info['materials'] > 0 and info['frame_end'] == 12, info)
    c.check('Texture incorporata, nessun collegamento esterno', info['images'] > 0 and not info['dependencies'], info)
    original_hash = hashlib.sha256(packed.read_bytes()).hexdigest()
    measured = json.loads(c.run('blender-cli', 'profile', packed, '--frame', 6))
    c.check('Profilazione preventiva senza modifiche al sorgente', measured['profile']['measured_pixels'] > 0
            and original_hash == hashlib.sha256(packed.read_bytes()).hexdigest(), measured['profile'])
    c.run('blender-cli', 'render', packed, preview, '--frame', 6)
    pixels = c.pixels(preview)
    c.check('Render CPU reale non uniforme', len(pixels) == 64 * 64 * 4 and len(set(pixels[::4])) > 10, len(pixels))
    c.run('blender-cli', 'export_glb', packed, glb)
    verify = c.root / 'reopen.py'
    verify.write_text("""import bpy
bpy.ops.wm.open_mainfile(filepath=NATIVE, use_scripts=False)
body=bpy.data.objects['EditableBody']
bpy.context.scene.frame_set(1); start=body.location.x
bpy.context.scene.frame_set(12); assert abs(body.location.x-start)>.4
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
assert any(o.type=='MESH' for o in bpy.data.objects)
assert any(o.animation_data for o in bpy.data.objects)
""".replace('NATIVE', repr(str(packed))).replace('GLB', repr(str(glb))))
    c.run('blender-cli', 'execute', verify)
    c.check('Animazione valutata e GLB reimportato', glb.read_bytes()[:4] == b'glTF', glb.stat().st_size)
    archive = c.root / 'sources.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(packed, 'Sources/scene.blend')
    helper = Path(__file__).resolve().parents[1] / 'righaven/source_packages.py'
    if not helper.exists():
        helper = Path('/opt/righaven-worker/source_packages.py')
    report = json.loads(c.run('python3', helper, 'verify', archive, '--native'))
    c.check('Sorgenti riaperti dopo trasferimento ZIP', any(x.get('check') == 'blender_reopen' and x['status'] == 'passed'
            for x in report['checks']), report)
    corrupt = c.root / 'work' / 'corrupt.blend'; corrupt.parent.mkdir(exist_ok=True)
    corrupt.write_bytes(b'This is not a Blender project')
    rejected = subprocess.run(['blender-cli', 'inspect', str(corrupt)], capture_output=True, text=True, timeout=60)
    c.check('File corrotto non accettato come progetto', rejected.returncode != 0, rejected.stderr[-400:])


def calibre(c):
    source, book, cover = [c.root / n for n in ('input.xhtml', 'book.epub', 'cover.png')]
    source.write_text('<html xmlns="http://www.w3.org/1999/xhtml" lang="it"><head><title>Prova</title></head>'
        '<body><h1>Prima parte</h1><p>' + MARKER + ' Città e qualità.</p>'
        '<h1>Seconda parte</h1><p>Contenuto da conservare.</p></body></html>')
    png(cover)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    c.batch([step('calibre.convert', input=str(source), output=str(book), epub_version='3', title='Collaudo Calibre',
                  authors='RigHaven Test', language='it', cover=str(cover)),
             step('calibre.inspect', input=str(book)), step('calibre.check', input=str(book))])
    info = json.loads(c.run('calibre-cli', 'inspect', book))
    c.check('Metadati e ordine di lettura nativi', info['title'] == ['Collaudo Calibre'] and info['languages'] == ['it'] and len(info['spine']) >= 2, info)
    with zipfile.ZipFile(book) as z:
        text = '\n'.join(z.read(n).decode('utf-8') for n in z.namelist() if n.endswith('.xhtml'))
        c.check('Testo originale e copertina incorporati', MARKER in text and 'Città' in text
                and any(n.endswith(('.jpg', '.png')) for n in z.namelist()), z.namelist())
    metadata, polished = c.root / 'metadata.epub', c.root / 'polished.epub'
    c.batch([step('calibre.metadata', input=str(book), output=str(metadata), title='Titolo aggiornato'),
             step('calibre.polish', input=str(metadata), output=str(polished), smarten_punctuation=True),
             step('calibre.check', input=str(polished))], 'refine')
    info = json.loads(c.run('calibre-cli', 'inspect', polished))
    c.check('Metadati persistono dopo polish', info['title'] == ['Titolo aggiornato'], info['title'])
    sources, rebuilt = c.root / 'Sources', c.root / 'rebuilt.epub'
    c.run('calibre-cli', 'unpack', polished, sources)
    chapter = next(p for p in sources.rglob('*.xhtml') if MARKER in p.read_text())
    chapter.write_text(chapter.read_text().replace(MARKER, MARKER + '-MODIFICATO'))
    c.run('calibre-cli', 'pack', sources, rebuilt)
    check = json.loads(c.run('calibre-cli', 'check', rebuilt))
    with zipfile.ZipFile(rebuilt) as z:
        modified = any((MARKER + '-MODIFICATO').encode() in z.read(n) for n in z.namelist() if n.endswith('.xhtml'))
    c.check('Sorgenti modificati e ricostruiti', modified and check['status'] == 'passed', check)
    azw3, pdf, docx = [c.root / n for n in ('book.azw3', 'book.pdf', 'book.docx')]
    c.batch([step('calibre.convert', input=str(book), output=str(azw3)), step('calibre.check', input=str(azw3)),
             step('calibre.convert', input=str(book), output=str(pdf)), step('calibre.convert', input=str(book), output=str(docx))], 'formats')
    with zipfile.ZipFile(docx) as z:
        c.check('DOCX contiene il testo', MARKER.encode() in z.read('word/document.xml'), 'word/document.xml')
    pdf_text = c.run('pdfcraft-cli', 'text', pdf)
    c.check('PDF con testo originale leggibile', pdf.read_bytes().startswith(b'%PDF-') and MARKER in pdf_text, pdf_text[-1000:])
    library, exported = c.root / 'library', c.root / 'library-export'
    c.batch([step('calibre.library', library=str(library), action='add', input=str(book))], 'library-add')
    listing = json.loads(c.run('calibre-cli', 'call', 'library', json.dumps({'library': str(library), 'action': 'list'})))['result']
    c.check('Libro presente nella libreria locale', len(listing) == 1 and listing[0]['title'] == 'Collaudo Calibre', listing)
    c.batch([step('calibre.library', library=str(library), action='export', output=str(exported), ids=[listing[0]['id']])], 'library-export')
    c.check('Export libreria contiene il libro', any(exported.rglob('*.epub')), str(exported))
    archive = c.root / 'Sources.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(rebuilt, 'publication.epub')
        for path in sources.rglob('*'):
            if path.is_file():
                z.write(path, 'Sources/' + path.relative_to(sources).as_posix())
    helper = Path(__file__).resolve().parents[1] / 'righaven/source_packages.py'
    if not helper.exists():
        helper = Path('/opt/righaven-worker/source_packages.py')
    report = json.loads(c.run('python3', helper, 'verify', archive, '--native'))
    c.check('Pacchetto trasferito e controllato nativamente', any(x['check'] == 'calibre_structure' and x['status'] == 'passed' for x in report['checks']), report)
    corrupt = c.root / 'corrupt.epub'; corrupt.write_bytes(b'not an epub')
    rejected = subprocess.run(['calibre-cli', 'check', str(corrupt)], capture_output=True, text=True, timeout=60)
    c.check('File corrotto non accettato', rejected.returncode != 0, rejected.stderr[-300:])
    # A valid ZIP with a missing referenced resource must also fail, not just a malformed container.
    missing = c.root / 'missing.epub'
    with zipfile.ZipFile(book) as src, zipfile.ZipFile(missing, 'w') as dst:
        for item in src.infolist():
            if not item.filename.endswith(('.jpg', '.png')):
                dst.writestr(item, src.read(item))
    rejected = subprocess.run(['calibre-cli', 'check', str(missing)], capture_output=True, text=True, timeout=60)
    c.check('Risorsa collegata mancante rilevata', rejected.returncode != 0, rejected.stdout[-1500:])
    c.check('Input originale intatto', hashlib.sha256(source.read_bytes()).hexdigest() == original, original)
    # Hand-authored interactive publications exercise CSS and non-linear spine
    # items differently from ebook-convert output (the observed Qt/GLX crash).
    interactive = c.root / 'interactive.epub'
    pages = {
        'nav':'<nav epub:type="toc"><h1>Indice</h1><ol><li><a href="cerca.xhtml">Inizia</a></li></ol></nav>',
        'cerca':'<h1>Scegli</h1><img src="cover.png" alt="Due colori"/><p><a href="blu.xhtml">Blu</a> <a href="rosso.xhtml">Rosso</a></p>',
        'blu':'<h1>Riprova</h1><a href="cerca.xhtml">Torna alla scelta</a>',
        'rosso':'<h1>Ben fatto</h1><a href="fine.xhtml">Continua</a>',
        'fine':'<h1>Fine</h1><a href="nav.xhtml">Indice</a>'}
    entries = {'mimetype':b'application/epub+zip',
        'META-INF/container.xml':b'<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        'EPUB/stile.css':b'body{margin:1em;color:#302a20}img{max-width:100%;height:auto}a{padding:.5em}'}
    items = ''.join(f'<item id="{name}" href="{name}.xhtml" media-type="application/xhtml+xml"' + (' properties="nav"' if name=='nav' else '') + '/>' for name in pages)
    spine = ''.join(f'<itemref idref="{name}" linear="' + ('yes' if name in ('cerca','fine') else 'no') + '"/>' for name in pages)
    entries['EPUB/package.opf'] = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">urn:uuid:11111111-1111-4111-8111-111111111111</dc:identifier><dc:title>Prova interattiva</dc:title><dc:language>it</dc:language><meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata><manifest>' + items + '<item id="css" href="stile.css" media-type="text/css"/><item id="image" href="cover.png" media-type="image/png"/></manifest><spine>' + spine + '</spine></package>').encode()
    entries['EPUB/cover.png'] = cover.read_bytes()
    for name, body in pages.items():
        entries[f'EPUB/{name}.xhtml'] = ('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="it"><head><title>Prova</title><link href="stile.css" rel="stylesheet" type="text/css"/></head><body>' + body + '</body></html>').encode()
    with zipfile.ZipFile(interactive,'w') as z:
        for name,data in entries.items():z.writestr(name,data)
    original = hashlib.sha256(interactive.read_bytes()).hexdigest()
    for repeat in range(3):
        check = json.loads(c.run('calibre-cli','check',interactive))
        c.check(f'EPUB interattivo controllato senza WebEngine, prova {repeat+1}',check['status']=='passed' and check.get('css_engine')=='calibre-bundled-stylelint-node',check)
    c.check('Collaudo non modifica EPUB interattivo',hashlib.sha256(interactive.read_bytes()).hexdigest()==original,original)
    broken = c.root / 'interactive-broken.epub'
    with zipfile.ZipFile(broken,'w') as z:
        for name,data in entries.items():
            z.writestr(name,data.replace(b'blu.xhtml',b'missing.xhtml') if name=='EPUB/cerca.xhtml' else data)
    rejected = subprocess.run(['calibre-cli','check',str(broken)],capture_output=True,text=True,timeout=60)
    c.check('Display virtuale rileva ancora link interattivo mancante',rejected.returncode!=0,rejected.stdout[-1500:])


CASES = {name: globals()[name] for name in ('photocraft', 'vectorcraft', 'filmcraft', 'lightcraft', 'pdfcraft',
            'effectcraft', 'designcraft', 'gridcraft', 'wordcraft', 'deckcraft', 'cadcraft', 'soundcraft', 'figcraft', 'blender', 'calibre')}
try:
    from .acceptance_toolkit import CASES as TOOLKIT_CASES
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from acceptance_toolkit import CASES as TOOLKIT_CASES
CASES.update(TOOLKIT_CASES)
try:
    from .acceptance_production import CASES as PRODUCTION_CASES
except ImportError:
    from acceptance_production import CASES as PRODUCTION_CASES
CASES.update(PRODUCTION_CASES)
try:
    from .acceptance_design import CASES as DESIGN_CASES
except ImportError:
    from acceptance_design import CASES as DESIGN_CASES
CASES.update(DESIGN_CASES)

try:
    from .acceptance_security import CASES as SECURITY_CASES
except ImportError:
    from acceptance_security import CASES as SECURITY_CASES
CASES.update(SECURITY_CASES)


try:from .acceptance_extended import CASES as EXTENDED_CASES
except ImportError:from acceptance_extended import CASES as EXTENDED_CASES
CASES.update(EXTENDED_CASES)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agents', nargs='+', choices=list(CASES), default=list(CASES))
    parser.add_argument('--output', type=Path, default=Path('/mnt/user-data/outputs/acceptance/report.json'))
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for app in args.agents:
        case = Case(output.parent, app)
        try:
            CASES[app](case)
            result = {'app': app, 'passed': True}
        except Exception as error:
            result = {'app': app, 'passed': False, 'error': str(error)}
        result.update(checks=case.checks, commands=case.commands,
            files=[{'path': str(p), 'bytes': p.stat().st_size,
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in case.root.rglob('*') if p.is_file()])
        results.append(result)
        output.write_text(json.dumps({'passed': len(results) == len(args.agents) and all(r['passed'] for r in results),
            'expected_cases': len(args.agents), 'completed_cases': len(results),
            'scope': 'Native deterministic workflows, not model performance or visual/audio review',
            'results': results}, ensure_ascii=False, indent=2) + '\n')
        print(('OK' if result['passed'] else 'FAIL'), app, result.get('error', ''), flush=True)
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
