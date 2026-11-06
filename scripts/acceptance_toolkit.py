"""Offline native acceptance for the nine optional-method toolkit applications."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import wave
import zipfile


def call(c, operation, **args):
    executable = 'whisper-cpp-cli' if c.app == 'whisper' else c.app + '-cli'
    text = c.run(executable, 'call', operation, json.dumps(args), timeout=300)
    return json.loads(text)


def rejected(c, operation, **args):
    executable = 'whisper-cpp-cli' if c.app == 'whisper' else c.app + '-cli'
    value = subprocess.run([executable, 'call', operation, json.dumps(args)], capture_output=True, text=True, timeout=120)
    c.check('Invalid operation/input is rejected', value.returncode != 0, (value.stdout + value.stderr)[-1000:])


def ffmpeg(c):
    video = c.root / 'video.mp4';audio = c.root / 'audio.wav'
    c.run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=25', '-t', '1', '-c:v', 'libx264', '-threads', '2', video)
    c.run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '1', audio)
    merged = c.root / 'merged.mp4';call(c, 'mux', input=str(video), audio=str(audio), output=str(merged))
    info = call(c, 'probe', input=str(merged), output=str(c.root / 'probe.json'))['media']
    c.check('Actual mux contains audio and video', {s['codec_type'] for s in info['streams']} == {'audio', 'video'}, info)
    decoded = c.root / 'decoded.wav';call(c, 'extract_audio', input=str(merged), output=str(decoded), sample_rate=16000, channels=1)
    probe = c.probe(decoded)['streams'][0]
    c.check('Audio extraction has requested PCM/rate/channels', probe['sample_rate'] == '16000' and probe['channels'] == 1 and probe['codec_name'] == 'pcm_s16le', probe)
    export = c.root / 'resized.mp4';call(c, 'transcode', input=str(merged), output=str(export), video_codec='libx264', audio_codec='aac', width=160, height=120, fps=20)
    stream = next(s for s in c.probe(export)['streams'] if s['codec_type'] == 'video')
    c.check('Native resized export matches requested dimensions/rate', stream['width'] == 160 and stream['height'] == 120 and stream['r_frame_rate'] == '20/1', stream)
    rejected(c, 'transcode', input=str(video), output=str(export))


def playwright(c):
    html = c.root / 'page.html'
    html.write_text('<!doctype html><title>Native browser</title><button onclick="this.textContent=\'Done\'">Start</button>')
    test = c.root / 'interaction.test.cjs'
    test.write_text("const {test,expect}=require('@playwright/test');\ntest('real click',async({page})=>{await page.goto(" + json.dumps(html.as_uri()) + ");await page.getByRole('button',{name:'Start'}).click();await expect(page.getByRole('button')).toHaveText('Done');});\n")
    result = c.root / 'tested'
    call(c, 'test', input=str(test), output=str(result))
    report = json.loads((result / 'report.json').read_text())
    c.check('Real browser click assertion passed', report['stats']['expected'] == 1 and report['stats']['unexpected'] == 0, report['stats'])
    png = c.root / 'screen.png'
    call(c, 'screenshot', url=html.as_uri(), output=str(png), width=640, height=480)
    c.check('PNG decoded from actual Chromium', len(c.pixels(png)) >= 640 * 480 * 4, str(png))
    bad = c.root / 'wrong.test.cjs';bad.write_text("const {test,expect}=require('@playwright/test');test('wrong',()=>expect(1).toBe(2));")
    rejected(c, 'test', input=str(bad), output=str(c.root / 'failed-test'))
    rejected(c, 'screenshot', url='file:///etc/passwd', output=str(c.root / 'outside.png'))


def aubio(c):
    wav = c.root / 'tone.wav'
    with wave.open(str(wav), 'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
        w.writeframes(b''.join(struct.pack('<h', int(12000 * math.sin(2 * math.pi * 440 * i / 44100))) for i in range(44100 * 2)))
    report = c.root / 'pitch.json';call(c, 'analyze', input=str(wav), output=str(report), feature='pitch')
    value = json.loads(report.read_text());pitches = [float(row[1]) for row in value['rows'] if len(row) >= 2 and float(row[1]) > 0]
    c.check('Measured pitch matches actual 440 Hz signal', len(pitches) > 20 and sum(abs(p - 440) < 5 for p in pitches) / len(pitches) > .7, pitches[:20])
    clicks = c.root / 'clicks.wav'
    with wave.open(str(clicks), 'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
        w.writeframes(b''.join(struct.pack('<h', int(20000 * math.sin(i * .8)) if i % 22050 < 500 else 0) for i in range(44100 * 5)))
    for feature in ('onset', 'beat', 'tempo', 'notes'):
        path = c.root / (feature + '.json');call(c, 'analyze', input=str(clicks), output=str(path), feature=feature)
        result = json.loads(path.read_text())
        units = result['tempo_unit'] == 'bpm' and result['time_unit'] is None if feature == 'tempo' else result['time_unit'] == 'seconds'
        c.check('Native ' + feature + ' analysis has explicit units', units and result['status'] == 'estimated', result['rows'][:10])
        if feature == 'onset': c.check('Click attacks detected', len(result['rows']) >= 5, result['rows'])
    rejected(c, 'analyze', input=str(wav), output=str(report), feature='pitch')


def fluidsynth(c):
    # Format-0 MIDI: explicit program, A4 for half a second at the default tempo.
    track = bytes.fromhex('00c00000903c648360803c0000ff2f00')
    midi = c.root / 'score.mid';midi.write_bytes(b'MThd' + struct.pack('>IHHH', 6, 0, 1, 480) + b'MTrk' + struct.pack('>I', len(track)) + track)
    original = hashlib.sha256(midi.read_bytes()).hexdigest()
    output = c.root / 'Sources';result = call(c, 'render', input=str(midi), output=str(output), gain=.4)
    wav = output / 'render.wav';probe = c.probe(wav)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(wav), '-f', 's16le', '-'], capture_output=True, check=True).stdout
    c.check('Real SoundFont render is non-silent stereo 48k', any(decoded) and probe['streams'][0]['sample_rate'] == '48000' and probe['streams'][0]['channels'] == 2, probe)
    relocated = c.root / 'Relocated';shutil.copytree(output, relocated)
    rebuilt = call(c, 'render', input=str(relocated / 'score.mid'), soundfont=str(relocated / 'bank.sf2'), output=str(c.root / 'rebuilt'), gain=.4)
    c.check('MIDI + bank rebuild after relocation', Path(rebuilt['audio']).read_bytes() == wav.read_bytes(), result['editable_sources'])
    c.check('Original score preserved', hashlib.sha256(midi.read_bytes()).hexdigest() == original, original)
    rejected(c, 'render', input=str(midi), output=str(output))


def pandoc(c):
    md = c.root / 'source.md';md.write_text('---\ntitle: Native round-trip\nlang: en\n---\n\n# Chapter\n\nrighaven-TOOLKIT **editable** content.\n')
    docx = c.root / 'book.docx';call(c, 'convert', input=str(md), output=str(docx))
    with zipfile.ZipFile(docx) as z:
        c.check('DOCX contains structured source text', b'righaven-TOOLKIT' in z.read('word/document.xml'), 'word/document.xml')
    back = c.root / 'back.md';call(c, 'convert', input=str(docx), output=str(back))
    c.check('Document reopens into editable Markdown', 'righaven-TOOLKIT' in back.read_text(), back.read_text())
    epub = c.root / 'book.epub';call(c, 'convert', input=str(md), output=str(epub))
    with zipfile.ZipFile(epub) as z:
        c.check('EPUB has actual content', any(b'righaven-TOOLKIT' in z.read(n) for n in z.namelist() if n.endswith('.xhtml')), z.namelist())
    rejected(c, 'convert', input=str(md), output=str(docx))


def epubcheck(c):
    md = c.root / 'source.md';md.write_text('---\ntitle: Conformance test\nlang: en\n---\n\n# Chapter\n\nA complete EPUB fixture.\n')
    epub = c.root / 'book.epub';c.run('pandoc', md, '-o', epub)
    report = c.root / 'valid.json';result = call(c, 'check', input=str(epub), output=str(report))
    c.check('Independent EPUB conformance passed', result['status'] == 'passed' and report.is_file(), result.get('report'))
    missing = c.root / 'missing.epub'
    with zipfile.ZipFile(epub) as src, zipfile.ZipFile(missing, 'w') as dst:
        skipped = False
        for item in src.infolist():
            if not skipped and item.filename.endswith('.xhtml') and 'nav' not in item.filename:
                skipped = True;continue
            dst.writestr(item, src.read(item))
    rejected(c, 'check', input=str(missing), output=str(c.root / 'invalid.json'))
    c.check('Missing referenced resource has real error report', bool(json.loads((c.root / 'invalid.json').read_text()).get('messages')), 'EPUBCheck JSON')


def typst(c):
    source = c.root / 'source.typ';source.write_text('#set page(width: 140mm, height: 200mm)\n#set text(font: "DejaVu Sans")\n= Native composition\nrighaven-TOOLKIT editable source.\n')
    pdf = c.root / 'book.pdf';call(c, 'compile', input=str(source), output=str(pdf))
    text = c.run('pdfcraft-cli', 'text', pdf)
    c.check('Compiled PDF has actual requested text', 'righaven-TOOLKIT' in text, text)
    relocated = c.root / 'Relocated';relocated.mkdir();shutil.copy2(source, relocated / source.name)
    edited = relocated / source.name;edited.write_text(edited.read_text().replace('editable source', 'modified source'))
    rebuilt = relocated / 'rebuilt.pdf';call(c, 'compile', input=str(edited), output=str(rebuilt))
    c.check('Relocated edited source rebuilds', 'modified source' in c.run('pdfcraft-cli', 'text', rebuilt), str(rebuilt))
    png = c.root / 'page.png';call(c, 'compile', input=str(source), output=str(png))
    c.check('Native page render decodes', len(c.pixels(png)) > 1000, str(png))
    bad = c.root / 'bad.typ';bad.write_text('#unknown-function()')
    rejected(c, 'compile', input=str(bad), output=str(c.root / 'bad.pdf'))


def freecad(c):
    script = c.root / 'build.py'
    script.write_text("import FreeCAD as App\nimport os\nfrom pathlib import Path\ndoc=App.newDocument('NativeFixture')\nbox=doc.addObject('Part::Box','Box')\nbox.Length=20;box.Width=10;box.Height=5\ndoc.recompute()\ndoc.saveAs(str(Path(os.environ['righaven_JOB_OUTPUT'])/'model.FCStd'))\nApp.closeDocument(doc.Name)\n")
    output = c.root / 'Sources';call(c, 'execute', input=str(script), output=str(output))
    model = output / 'model.FCStd';inspection = call(c, 'inspect', input=str(model), output=str(c.root / 'inspect.json'))['inspection']
    box = next(x for x in inspection['objects'] if x['name'] == 'Box')
    c.check('Native parametric dimensions and solid volume preserved', box['type'] == 'Part::Box' and box['valid'] and abs(box['volume'] - 1000) < .01 and box['dimensions_mm']['Length'] == 20, box)
    relocated = c.root / 'relocated.FCStd';shutil.copy2(model, relocated)
    edit = c.root / 'edit.py';edit.write_text("import FreeCAD as App\nimport os\nfrom pathlib import Path\ndoc=App.openDocument(" + repr(str(relocated)) + ")\ndoc.Box.Length=30\ndoc.recompute()\nassert abs(doc.Box.Shape.Volume-1500)<0.01\ndoc.saveAs(str(Path(os.environ['righaven_JOB_OUTPUT'])/'modified.FCStd'))\nApp.closeDocument(doc.Name)\n")
    edited = c.root / 'Edited';call(c, 'execute', input=str(edit), output=str(edited))
    again = call(c, 'inspect', input=str(edited / 'modified.FCStd'), output=str(c.root / 'modified.json'))['inspection']
    c.check('Transferred source is editable and recomputed natively', abs(next(x for x in again['objects'] if x['name'] == 'Box')['volume'] - 1500) < .01, again)
    step = c.root / 'model.step';call(c, 'export_step', input=str(model), output=str(step))
    verify = c.root / 'verify.py';verify.write_text("import Part\ns=Part.read(" + repr(str(step)) + ")\nassert s.isValid() and abs(s.Volume-1000)<0.01\n")
    call(c, 'execute', input=str(verify), output=str(c.root / 'step-check'))
    c.check('STEP reopened with native geometry kernel', step.stat().st_size > 100, str(step))
    archive = c.root / 'Sources.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(model, 'CAD/model.FCStd');z.write(script, 'CAD/build.py')
    helper = Path(__file__).resolve().parents[1] / 'righaven/source_packages.py'
    if not helper.exists(): helper = Path('/opt/righaven-worker/source_packages.py')
    report = json.loads(c.run('python3', helper, 'verify', archive, '--native'))
    c.check('Native CAD source reopened from transferred ZIP', any(x['check'] == 'freecad_reopen' and x['status'] == 'passed' for x in report['checks']), report)
    parametric = c.root / 'sketch-pad.py'
    parametric.write_text("""import FreeCAD as App
import Part, Sketcher, os
from pathlib import Path
doc=App.newDocument('ParametricFixture')
body=doc.addObject('PartDesign::Body','Body')
sketch=body.newObject('Sketcher::SketchObject','Profile')
points=[(0,0),(20,0),(20,10),(0,10)]
for i in range(4):
    a,b=points[i],points[(i+1)%4]
    sketch.addGeometry(Part.LineSegment(App.Vector(*a,0),App.Vector(*b,0)),False)
for i in range(4):sketch.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%4,1))
for i in (0,2):sketch.addConstraint(Sketcher.Constraint('Horizontal',i))
for i in (1,3):sketch.addConstraint(Sketcher.Constraint('Vertical',i))
sketch.addConstraint(Sketcher.Constraint('Coincident',0,1,-1,1))
width=sketch.addConstraint(Sketcher.Constraint('Distance',0,20.0))
sketch.addConstraint(Sketcher.Constraint('Distance',1,10.0))
sketch.renameConstraint(width,'width')
pad=body.newObject('PartDesign::Pad','Pad');pad.Profile=sketch;pad.Length=5
doc.recompute()
assert abs(body.Shape.Volume-1000)<.01 and sketch.FullyConstrained
sketch.setDatum(width,App.Units.Quantity('30 mm'));doc.recompute()
assert abs(body.Shape.Volume-1500)<.01
doc.saveAs(str(Path(os.environ['righaven_JOB_OUTPUT'])/'parametric.FCStd'))
App.closeDocument(doc.Name)
""")
    advanced = c.root / 'Parametric';call(c, 'execute', input=str(parametric), output=str(advanced))
    advanced_step = c.root / 'parametric.step';call(c, 'export_step', input=str(advanced / 'parametric.FCStd'), output=str(advanced_step))
    verify_pad = c.root / 'verify-pad.py';verify_pad.write_text('import Part\ns=Part.read(' + repr(str(advanced_step)) + ')\nassert s.isValid() and len(s.Solids)==1 and abs(s.Volume-1500)<.01\n')
    call(c, 'execute', input=str(verify_pad), output=str(c.root / 'parametric-proof'))
    c.check('Constrained sketch/Pad editable; STEP contains one final solid without duplicates', advanced_step.is_file(), str(advanced_step))
    broken = c.root / 'broken.FCStd';broken.write_bytes(b'not a native project')
    rejected(c, 'inspect', input=str(broken), output=str(c.root / 'broken.json'))


def whisper(c):
    source = Path(os.environ.get('RIGHAVEN_INSTALL_ROOT', '/opt/righaven')) / 'apps/whisper/jfk.wav'
    wav = c.root / 'speech.wav';shutil.copy2(source, wav)
    output = c.root / 'transcription';result = call(c, 'transcribe', input=str(wav), output=str(output), language='en')
    c.check('Actual CPU transcription recognizes speech fixture', 'country' in result['transcript'].lower(), result['transcript'])
    c.check('Editable subtitles contain timecodes', '-->' in (output / 'transcript.srt').read_text(), (output / 'transcript.srt').read_text())
    rejected(c, 'transcribe', input=str(wav), output=str(output))


CASES = {name: globals()[name] for name in ('ffmpeg', 'playwright', 'aubio', 'fluidsynth', 'epubcheck', 'pandoc', 'typst', 'freecad', 'whisper')}
