"""Native acceptance for complementary production tools; no model or credentials."""
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
try:
    from .acceptance_toolkit import call, rejected
except ImportError:
    from acceptance_toolkit import call, rejected


def source_zip(c,folder,check):
    archive=c.root/(folder.name+'-Sources.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in folder.rglob('*'):
            if path.is_file():z.write(path,path.relative_to(folder).as_posix())
    helper=Path(__file__).resolve().parents[1]/'righaven/source_packages.py'
    if not helper.exists():helper=Path('/opt/righaven-worker/source_packages.py')
    report=json.loads(c.run('python3',helper,'verify',archive,'--native'))
    c.check('Delivery verifier reopens transferred native source ZIP',any(x['check']==check and x['status']=='passed' for x in report['checks']),report)


def musescore(c):
    source=c.root/'score.musicxml'
    source.write_text('''<?xml version="1.0"?><score-partwise version="4.0"><work><work-title>Native score fixture</work-title></work><part-list><score-part id="P1"><part-name>Piano</part-name><score-instrument id="I1"><instrument-name>Piano</instrument-name></score-instrument><midi-instrument id="I1"><midi-channel>1</midi-channel><midi-program>1</midi-program></midi-instrument></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><direction><sound tempo="120"/></direction><note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note><note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note><note><pitch><step>G</step><octave>4</octave></pitch><duration>2</duration><type>half</type></note></measure></part></score-partwise>''')
    native=c.root/'score.mscz';call(c,'convert',input=str(source),output=str(native))
    moved=c.root/'relocated';moved.mkdir();shutil.copy2(native,moved/native.name)
    info=call(c,'inspect',input=str(moved/native.name),output=str(c.root/'score-info.json'))['inspection']['metadata']
    c.check('Native score reopens after relocation with notes and tempo',info['measures']==1 and info['tempo']==120 and len(info['parts'])==1,info)
    source_zip(c,moved,'musescore_reopen')
    with zipfile.ZipFile(native) as z:
        xml=z.read(next(n for n in z.namelist() if n.endswith('.mscx'))).decode()
    c.check('Editable score retains actual three notes',xml.count('<Note>')==3,xml.count('<Note>'))
    for ext in ('mid','pdf','wav'):
        out=c.root/('score.'+ext);call(c,'convert',input=str(native),output=str(out))
        c.check('Native '+ext+' export is nonempty',out.stat().st_size>100,out.stat().st_size)
    pcm=subprocess.run(['ffmpeg','-v','error','-i',str(c.root/'score.wav'),'-f','s16le','-'],capture_output=True,check=True,timeout=60).stdout
    c.check('Actual score audio contains a signal',len(pcm)>48000 and any(pcm),len(pcm))
    bad=c.root/'invalid.musicxml';bad.write_text('not a score')
    rejected(c,'convert',input=str(bad),output=str(c.root/'bad.mscz'))


def ifcopenshell(c):
    script=c.root/'building.py';script.write_text('''import ifcopenshell, ifcopenshell.api, os
from pathlib import Path
m=ifcopenshell.api.run('project.create_file',version='IFC4')
p=ifcopenshell.api.run('root.create_entity',m,ifc_class='IfcProject',name='Native BIM fixture')
ifcopenshell.api.run('unit.assign_unit',m)
b=ifcopenshell.api.run('root.create_entity',m,ifc_class='IfcBuilding',name='Building')
ifcopenshell.api.run('aggregate.assign_object',m,products=[b],relating_object=p)
m.write(str(Path(os.environ['righaven_JOB_OUTPUT'])/'building.ifc'))
''')
    output=c.root/'authored';call(c,'execute',input=str(script),output=str(output))
    native=output/'building.ifc';moved=c.root/'relocated';shutil.copytree(output,moved)
    info=call(c,'check',input=str(moved/native.name),output=str(c.root/'ifc-check.json'))['inspection']
    c.check('Relocated IFC schema validates and retains semantic project/building',info['status']=='passed' and info['projects'][0]['name']=='Native BIM fixture' and info['entity_counts']['IfcBuilding']==1,info)
    c.check('Native IFC unit declarations are inspected',bool(info.get('units')) and any(u.get('UnitType')=='LENGTHUNIT' for group in info['units'] for u in group),info.get('units'))
    c.check('Actual authoring source retained',(moved/'Sources/building.py').read_text()==script.read_text(),str(moved))
    source_zip(c,moved,'ifcopenshell_reopen')
    library=c.root/'library.py';library.write_text("import ifcopenshell,ifcopenshell.api,os\nfrom pathlib import Path\nm=ifcopenshell.api.run('project.create_file',version='IFC4')\nifcopenshell.api.run('root.create_entity',m,ifc_class='IfcProjectLibrary',name='Reusable components')\nm.write(str(Path(os.environ['righaven_JOB_OUTPUT'])/'library.ifc'))\n")
    authored_library=c.root/'library';call(c,'execute',input=str(library),output=str(authored_library))
    # An IFC library is a valid reusable source without a full building/project.
    source_zip(c,authored_library,'ifcopenshell_reopen')
    bad=c.root/'invalid.ifc';bad.write_text('not IFC');rejected(c,'check',input=str(bad),output=str(c.root/'bad.json'))


def manim(c):
    resources=c.root/'resources';resources.mkdir()
    (resources/'label.txt').write_text('Native animation')
    script=resources/'scene.py';script.write_text('''from manim import *
from pathlib import Path
class NativeScene(Scene):
    def construct(self):
        self.add(Text(Path(__file__).with_name('label.txt').read_text(),font_size=22))
        dot=Dot(LEFT*2,color=RED);self.add(dot)
        self.play(dot.animate.shift(RIGHT*4),run_time=1,rate_func=linear)
''')
    out=c.root/'rendered';call(c,'render',input=str(script),output=str(out),scene='NativeScene',quality='draft',resource_dir=str(resources))
    moved=c.root/'relocated';shutil.copytree(out,moved)
    rerender=c.root/'rerendered';call(c,'render',input=str(moved/'Sources/scene.py'),output=str(rerender),scene='NativeScene',quality='draft',resource_dir=str(moved/'Sources'))
    video=next(p for p in (rerender/'Render').rglob('*.mp4') if 'partial_movie_files' not in p.parts)
    stream=c.probe(video)['streams'][0]
    c.check('Relocated scene and resources actually render on CPU',stream['width']==854 and stream['height']==480 and float(stream['duration'])>=.9,stream)
    a=c.pixels(video,time=.1);b=c.pixels(video,time=.8)
    c.check('Rendered frames contain actual animation',a!=b and len(a)==854*480*4,len(a))
    rejected(c,'render',input=str(script),output=str(c.root/'bad'),scene='MissingScene',quality='draft')


def opentimelineio(c):
    media=c.root/'media';media.mkdir()
    c.run('ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=25','-t','1','-c:v','libx264','-threads','2',media/'clip.mp4')
    script=c.root/'timeline.py';script.write_text('''import opentimelineio as otio,os
from pathlib import Path
r=otio.opentime.TimeRange(otio.opentime.RationalTime(0,25),otio.opentime.RationalTime(25,25))
t=otio.schema.Timeline(name='Native timeline')
track=otio.schema.Track(name='Picture',kind=otio.schema.TrackKind.Video);t.tracks.append(track)
track.append(otio.schema.Clip(name='Clip',source_range=r,media_reference=otio.schema.ExternalReference(target_url='../media/clip.mp4',available_range=r)))
otio.adapters.write_to_file(t,str(Path(os.environ['righaven_JOB_OUTPUT'])/'timeline.otio'))
''')
    authored=c.root/'authored';call(c,'execute',input=str(script),output=str(authored))
    timeline=authored/'timeline.otio'
    info=call(c,'check',input=str(timeline),output=str(c.root/'checked.json'))['inspection']
    c.check('Native rational timeline and media validate',info['status']=='passed' and info['duration_seconds']==1,info)
    packed=c.root/'packed';call(c,'pack',input=str(timeline),output=str(packed))
    moved=c.root/'relocated';shutil.copytree(packed,moved)
    shutil.rmtree(media)
    info=call(c,'check',input=str(moved/'Timeline.otiod/content.otio'),output=str(c.root/'moved.json'))['inspection']
    c.check('Relocated native bundle retains actual media without originals',info['status']=='passed' and len(info['clips'])==1,info)
    source_zip(c,moved,'opentimelineio_reopen')
    next((moved/'Timeline.otiod/media').rglob('*.mp4')).unlink()
    rejected(c,'check',input=str(moved/'Timeline.otiod/content.otio'),output=str(c.root/'missing.json'))


def pymeshlab(c):
    mesh=c.root/'original.obj';mesh.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 0\nf 1 2 3\n')
    filters=c.root/'clean.mlx';filters.write_text('<!DOCTYPE FilterScript><FilterScript><filter name="Remove Duplicate Vertices"/></FilterScript>')
    out=c.root/'repaired';call(c,'apply',input=str(mesh),filters=str(filters),output=str(out))
    info=json.loads((out/'inspection.json').read_text())
    c.check('Native mesh cleanup actually removes duplicate vertices',info['before']['vertices']==4 and info['after']['vertices']==3,info)
    moved=c.root/'relocated';shutil.copytree(out,moved);shutil.rmtree(out)
    info=call(c,'inspect',input=str(moved/'project.mlp'),output=str(c.root/'mesh-check.json'))['inspection']
    c.check('Relocated MLP opens with actual geometry',info['vertices']==3 and info['faces']==1,info)
    c.check('Editable filter and original geometry retained',(moved/'procedure.mlx').is_file() and (moved/'Sources/original.obj').is_file(),str(moved))
    source_zip(c,moved,'pymeshlab_reopen')
    next(moved.glob('mesh.ply')).unlink()
    rejected(c,'inspect',input=str(moved/'project.mlp'),output=str(c.root/'missing.json'))


CASES={fn.__name__:fn for fn in (musescore,ifcopenshell,manim,opentimelineio,pymeshlab)}
