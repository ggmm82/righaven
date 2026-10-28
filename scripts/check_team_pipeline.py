#!/usr/bin/env python3
"""Real Photo→Effect→Sound→Film file exchange, using tiny declared fixtures.

This verifies tool interoperability, not robot artistry or an authenticated LLM.
Run inside the sandbox image (or with its native binaries on PATH).
"""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.acceptance import Case, png, step
from righaven.projects import create_plan, execute_step, read_project
from righaven.work_results import validate_media
from righaven.source_packages import pack
from righaven.deliveries import build_delivery


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--simulate-audio-interruption', action='store_true', help='Keep a real exported mix usable after an interrupted worker')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    create_plan(root, 'Fixture: asset animato e audio sincronizzati', [
        {'id': 'visual', 'agent': 'photocraft', 'goal': 'Asset immagine modificabile', 'depends_on': []},
        {'id': 'motion', 'agent': 'effectcraft', 'goal': 'Animazione dell’asset importato', 'depends_on': ['visual']},
        {'id': 'audio', 'agent': 'soundcraft', 'goal': 'Sessione e mix della stessa durata', 'depends_on': ['motion']},
        {'id': 'final', 'agent': 'filmcraft', 'goal': 'Timeline video e audio sovrapposti', 'depends_on': ['motion', 'audio']},
    ], 'animated_video')
    results, commands = {}, []

    def execute(sid, agent, produce):
        c = Case(root / 'outputs', agent)
        produced = []
        def invoke(task, started):
            started(str(c.root))
            inputs, outputs = produce(c)
            produced.extend(outputs)
            commands.extend(c.commands)
            handoff = {'task': 'Technical integration fixture', 'source_files': [str(p) for p in inputs], 'output_files': [str(p) for p in outputs],
                'checks': c.checks, 'delivery': {'source_status': 'included', 'source_note': 'Native source fixture', 'files': [
                    {'path': str(p), 'role': 'source_archive' if p.suffix == '.zip' else 'export' if p.suffix == '.mp4' else 'editable_source',
                     'reopen': {'status': 'passed'}} for p in outputs]}}
            # Every returned path must be a real, nonempty file.
            assert all(p.is_file() and p.stat().st_size for p in [*inputs, *outputs])
            if sid == 'audio' and args.simulate_audio_interruption:
                return json.dumps({'ok': False, 'output_dir': str(c.root), 'available_files': [str(p) for p in outputs],
                                   'error': 'Limite dei turni DeepSeek prima della chiusura formale'})
            verified = []
            if sid == 'final':
                checks = validate_media(outputs[-1], {'audio': True, 'video': True})
                assert all(check['status'] == 'passed' for check in checks), checks
                verified = [str(outputs[-1])]
            record = build_delivery(handoff, c.root, purpose='delivery') if sid == 'final' else None
            if record:
                record.update(requirements={'video': True, 'audio': True}, verified_products=verified)
                assert record['technical_status'] == 'passed', record['issues']
            return json.dumps({'ok': True, 'output_dir': str(c.root), 'handoff': handoff, 'delivery_record': record,
                               'product_verified': bool(verified), 'verified_products': verified})
        value = json.loads(execute_step(root, agent, 'Execute declared native fixture', sid, invoke,
                                       purpose='delivery' if sid == 'final' else 'work'))
        assert value['ok'] or (sid == 'audio' and args.simulate_audio_interruption), value
        results[sid] = produced

    def photo(c):
        source, native, exported = [c.root / n for n in ('input.png', 'asset.pcraft', 'asset.png')]
        png(source)
        c.run('photocraft-cli', 'convert', source, native)
        c.run('photocraft-cli', 'info', native)
        c.run('photocraft-cli', 'convert', native, exported)
        c.check('Asset esportato e sorgente riaperto', c.pixels(source) == c.pixels(exported), str(exported))
        return [source], [native, exported]

    def motion(c):
        asset = results['visual'][1]
        native, video = c.root / 'animation.ecproj', c.root / 'animation.mp4'
        code = ('var c=app.project.items.addComp("Main",160,90,1,0.6,10);'
                'var f=app.project.importFile(new ImportOptions(new File(' + json.dumps(str(asset)) + ')));'
                'var l=c.layers.add(f);'
                'l.property("Transform").property("Position").setValueAtTime(0,[40,45]);'
                'l.property("Transform").property("Position").setValueAtTime(0.5,[120,45]);')
        c.run('effectcraft-cli', '--empty', '--save-as', native, 'script', '--eval', code)
        c.run('effectcraft-cli', '--project', native, 'info')
        c.run('effectcraft-cli', '--project', native, 'render', '--comp', 'Main', '--out', video,
              '--format', 'h264', '--start', '0', '--end', '.6', '--fps', '10')
        a, b = c.pixels(video, 0), c.pixels(video, .5)
        c.check('Asset PhotoCraft animato e progetto riaperto', a != b and len(a) == 160 * 90 * 4, str(video))
        return [asset], [native, video]

    def audio(c):
        video = results['motion'][1]
        duration = float(c.probe(video)['format']['duration'])
        frames = round(duration * 48000)
        source, native, mixed = c.root / 'pulse.wav', c.root / 'session.scraft', c.root / 'mix.wav'
        with wave.open(str(source), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
            wav.writeframes(b''.join(struct.pack('<h', int(6500 * math.sin(2 * math.pi * 440 * i / 48000)))
                                     for i in range(frames)))
        c.batch([step('new_session', name='Team fixture', template='blank', sample_rate=48000),
                 step('import_audio', path=str(source)), step('save_session', path=str(native)),
                 step('bounce_mix', path=str(mixed), start=0, end=frames, bit_depth='16', format='wav')])
        c.run('soundcraft-cli', 'run', '--in', native, '--inspect')
        with wave.open(str(mixed), 'rb') as wav:
            c.check('Mix della durata dell’animazione', abs(wav.getnframes() / wav.getframerate() - duration) < .01,
                    {'duration': duration, 'frames': wav.getnframes()})
        return [video], [native, mixed]

    def film(c):
        video, audio = results['motion'][1], results['audio'][1]
        native, final = c.root / 'final.fcproj', c.root / 'final.mp4'
        c.batch([step('command_run', id='file.newProject', params={'name': 'Integrated team fixture'}),
                 step('media_import', paths=[str(video), str(audio)]),
                 step('command_run', id='file.newSequence', params={'name': 'Main', 'width': 160, 'height': 90, 'fps': 10}),
                 step('command_run', id='timeline.place', params={
                     'item': {'$result': '1.content.0.text.$json.items.0'}, 'track': 'V1',
                     'seconds': 0, 'insert': False, 'video': True, 'audio': False}),
                 step('command_run', id='timeline.place', params={
                     'item': {'$result': '1.content.0.text.$json.items.1'}, 'track': 'A1',
                     'seconds': 0, 'insert': False, 'video': False, 'audio': True}),
                 step('command_run', id='file.saveAs', params={'path': str(native)})])
        c.run('filmcraft-cli', '--project', native, 'inspect')
        c.run('filmcraft-cli', '--project', native, 'export', final, '--gpu-rendering', 'off')
        streams = c.probe(final)['streams']
        v = next(s for s in streams if s['codec_type'] == 'video')
        a = next(s for s in streams if s['codec_type'] == 'audio')
        c.check('Timeline con video e audio della stessa durata', v['width'] == 160 and v['height'] == 90
                and abs(float(v['duration']) - .6) < .08 and abs(float(a['duration']) - float(v['duration'])) < .08,
                {'video': v['duration'], 'audio': a['duration']})
        raw = c.run('ffmpeg', '-v', 'info', '-i', final, '-af', 'volumedetect', '-vn', '-f', 'null', '-')
        # volumedetect writes stderr: inspect the recorded command, not stdout.
        evidence = c.commands[-1]['stderr']
        c.check('Audio finale non silenzioso', 'mean_volume:' in evidence and 'mean_volume: -inf' not in evidence,
                evidence[-600:])
        c.check('Movimento preservato dopo il montaggio', c.pixels(final, 0) != c.pixels(final, .5), str(final))
        archive = pack(native, c.root / 'Sorgenti.zip', root)
        return [video, audio], [native, archive, final]

    for sid, agent, produce in [('visual', 'photocraft', photo), ('motion', 'effectcraft', motion),
                                ('audio', 'soundcraft', audio), ('final', 'filmcraft', film)]:
        execute(sid, agent, produce)
    plan = read_project(root)
    assert all(s['status'] == ('paused' if s['id'] == 'audio' and args.simulate_audio_interruption else 'completed') for s in plan['steps'])
    from righaven.projects import create_plan as update_project
    plan = update_project(root, '', [], status='review', product_path=str(results['final'][-1]), summary='Video con audio verificato tecnicamente')
    try:
        update_project(root, '', [], status='ready')
    except ValueError as error:
        assert 'revisione separata' in str(error), error
    else:
        raise AssertionError('Technical fixtures cannot certify artistic quality')
    assert plan['status'] == 'review'
    # A valid but unrelated export must not inherit the source package proof.
    wrong = root / 'wrong-version.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=white:size=160x90:rate=10',
                    '-t', '0.6', '-c:v', 'libx264', str(wrong)], check=True)
    mismatch = build_delivery({'task': 'Wrong version regression', 'checks': [], 'delivery': {
        'source_status': 'included', 'source_note': 'Real native package, wrong export', 'files': [
            {'path': str(results['final'][1]), 'role': 'source_archive', 'reopen': {'status': 'passed'}},
            {'path': str(wrong), 'role': 'export', 'reopen': {'status': 'passed'}}]}}, root, purpose='delivery')
    assert mismatch['technical_status'] == 'needs_revision' and any('non corrisponde' in s for s in mismatch['issues']), mismatch
    (root / 'report.json').write_text(json.dumps({'fixture': True, 'project': plan, 'commands': commands}, indent=2))
    print('Native collaboration OK: asset, animation and real mix integrated in FilmCraft; final video/audio validated; interrupted audio does not block delivery:', args.simulate_audio_interruption)


if __name__ == '__main__':
    main()
