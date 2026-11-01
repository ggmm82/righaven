#!/usr/bin/env python3
"""Supervised file-based CLI/MCP adapters for the open-source toolkit."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlparse, unquote

try:
    from .toolkit_specs import TOOLS
except ImportError:
    from toolkit_specs import TOOLS
try:
    from operations import supervise, folder
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from righaven.operations import supervise, folder

ROOT = Path(os.environ.get('RIGHAVEN_WORKSPACE_ROOT', '/mnt/user-data')).resolve()
INSTALL = Path(os.environ.get('RIGHAVEN_INSTALL_ROOT', '/opt/righaven')).resolve()
HERE = Path(__file__).resolve().parent


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def scoped(value, *, exists=True, directory=False, fresh=False):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        raise ValueError('Path must be an absolute workspace path without external links: ' + str(value))
    path = path.resolve()
    if fresh and path.exists():
        raise ValueError('Refusing to overwrite an existing output: ' + str(value))
    if (exists or path.exists()) and not (path.is_dir() if directory else path.is_file()):
        raise ValueError('Input missing or wrong path type: ' + str(value))
    return path


def checked_args(app, action, args):
    spec = next((t['inputSchema'] for t in TOOLS[app] if t['name'] == app + '.' + action), None)
    if not spec or not isinstance(args, dict) or set(args) - spec['properties'].keys() or set(spec['required']) - args.keys():
        raise ValueError('Unknown operation, missing or unsupported arguments')
    for name, value in args.items():
        field = spec['properties'][name]
        types = {'string': (str,), 'integer': (int,), 'number': (float, int), 'boolean': (bool,), 'array': (list,)}
        if type(value) not in types[field['type']]:
            raise ValueError('Wrong argument type: ' + name)
        if field['type'] == 'array':
            item = field.get('items', {})
            if (len(value) > 50 or len(value) < field.get('minItems', 0) or field.get('uniqueItems') and len(set(map(str, value))) != len(value)
                    or any(type(v) not in types[item.get('type', 'string')] or 'enum' in item and v not in item['enum'] for v in value)):
                raise ValueError('Argument outside supported values: ' + name)
            continue
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('A finite numeric value is required: ' + name)
        if isinstance(value, str) and (not value.strip() or len(value) > 4000 or '\0' in value):
            raise ValueError('Empty or excessive argument: ' + name)
        if ('enum' in field and value not in field['enum'] or 'minimum' in field and value < field['minimum']
                or 'maximum' in field and value > field['maximum']):
            raise ValueError('Argument outside supported values: ' + name)


def run(app, argv, root, *, env=None, allow_failure=False):
    argv = list(map(str, argv))
    if env:
        argv = ['/usr/bin/env', *[k + '=' + str(v) for k, v in env.items()], *argv]
    key = app + '-' + hashlib.sha256(json.dumps(argv).encode()).hexdigest()
    result, stats = supervise(argv, root, key, timeout=1200, label=app + ' · native operation')
    if result.returncode and not allow_failure:
        raise RuntimeError(('Memory exhausted. ' if stats.get('oom_kills') else '') +
                           app + f' exited {result.returncode}: ' + (result.stdout + result.stderr)[-3500:])
    return result


def freecad_command(*args):
    # Use the Python ABI and native libraries shipped in the official AppImage.
    prefix = INSTALL / 'apps/freecad/squashfs-root/usr'
    return ['/usr/bin/env', 'PYTHONHOME=' + str(prefix),
            'PYTHONPATH=' + str(prefix / 'lib'), 'PATH_TO_FREECAD_LIBDIR=' + str(prefix / 'lib'),
            'QT_QPA_PLATFORM=offscreen', str(prefix / 'bin/python'),
            str(HERE / 'toolkit_job.py'), *map(str, args)]


def native_version(app):
    try:from .extended_tools import APPS as EXTENDED_APPS, version as extended_version
    except ImportError:from extended_tools import APPS as EXTENDED_APPS, version as extended_version
    if app in EXTENDED_APPS:return extended_version(app,sys.modules[__name__])
    if app in ('opengrep','trivy'):
        try:from .security_tools import version
        except ImportError:from security_tools import version
        return version(app,sys.modules[__name__])
    if app in ('d2','plantuml','mermaid','excalidraw','bpmn','structurizr'):
        try:from .design_tools import version
        except ImportError:from design_tools import version
        return version(app,sys.modules[__name__])
    if app in ('musescore','ifcopenshell','manim','opentimelineio','pymeshlab'):
        try: from .production_tools import version
        except ImportError: from production_tools import version
        return version(app, INSTALL, HERE)
    commands = {
        'playwright': ['node', str(INSTALL / 'toolkit/node_modules/playwright/cli.js'), '--version'],
        'aubio': ['aubio', '--version'], 'fluidsynth': ['fluidsynth', '--version'],
        'pandoc': ['pandoc', '--version'], 'typst': ['typst', '--version'],
        'ffmpeg': ['ffmpeg', '-version'],
        'freecad': freecad_command('version', '-', '-'),
    }
    if app == 'epubcheck': commands[app] = ['java', '-Xmx512m', '-jar', str(epub_jar()), '--version']
    if app == 'whisper':
        # Upstream whisper-cli has no --version. Verify the installed, hashed build,
        # and load its real help instead of reporting a fictitious native version.
        installed = json.loads((INSTALL / 'installed.json').read_text())
        entry = next(a for a in installed if a['id'] == app)
        subprocess.run(['whisper-cli', '--help'], capture_output=True, check=True, timeout=30)
        print('whisper.cpp ' + entry['version'] + ' source SHA256 ' + entry['sha256']); return
    result = subprocess.run(commands[app], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:] or result.stdout[-2000:])
    print(result.stdout + result.stderr)


def capture(app, argv, target, root):
    """Do not parse the supervisor's intentionally truncated log as a full result."""
    return run(app, [sys.executable, HERE / 'toolkit_capture.py', target, json.dumps(list(map(str, argv)))], root)


def epub_jar():
    jars = list((INSTALL / 'apps/epubcheck').rglob('epubcheck.jar'))
    if len(jars) != 1:
        raise RuntimeError('Expected one installed EPUBCheck jar')
    return jars[0]


def invoke(app, action, args):
    try:from .extended_tools import APPS as EXTENDED_APPS, invoke as extended_invoke
    except ImportError:from extended_tools import APPS as EXTENDED_APPS, invoke as extended_invoke
    if app in EXTENDED_APPS:
        checked_args(app,action,args)
        return extended_invoke(app,action,args,sys.modules[__name__])
    if app in ('opengrep','trivy'):
        checked_args(app,action,args)
        try:from .security_tools import invoke as scan
        except ImportError:from security_tools import invoke as scan
        return scan(app,action,args,sys.modules[__name__])
    checked_args(app, action, args)
    if app in ('d2','plantuml','mermaid','excalidraw','bpmn','structurizr'):
        try:from .design_tools import invoke as design_invoke
        except ImportError:from design_tools import invoke as design_invoke
        return design_invoke(app,action,args,sys.modules[__name__])
    if app in ('musescore','ifcopenshell','manim','opentimelineio','pymeshlab'):
        try: from .production_tools import invoke as production_invoke
        except ImportError: from production_tools import invoke as production_invoke
        return production_invoke(app,action,args,sys.modules[__name__])
    source = scoped(args['input']) if 'input' in args else None
    directories = (app in ('playwright', 'fluidsynth', 'whisper') and action != 'screenshot'
                   or app == 'freecad' and action == 'execute')
    output = scoped(args['output'], exists=False, directory=directories, fresh=True)
    if app == 'playwright':
        if source and (source.suffix != '.cjs' or action == 'test' and not source.name.endswith('.test.cjs')):
            raise ValueError('Use an explicit local .cjs script or *.test.cjs test')
        if action == 'screenshot':
            url = urlparse(args['url'])
            if url.scheme == 'file':
                if url.netloc: raise ValueError('Remote file URLs are not supported')
                scoped(unquote(url.path))
            elif url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
                raise ValueError('Use an HTTP(S) URL without embedded credentials, or a workspace file URL')
            if output.suffix.lower() != '.png': raise ValueError('Screenshot output must be PNG')
    suffixes = {'aubio': {'.json'}, 'epubcheck': {'.json'}, 'pandoc': {'.docx', '.epub', '.html', '.md', '.tex', '.typ', '.json', '.odt', '.rst', '.txt'},
                'typst': {'.pdf', '.png', '.svg'}}
    if app in suffixes and output.suffix.lower() not in suffixes[app]:
        raise ValueError('Unsupported output format; consult the native CLI for advanced workflows')
    if app == 'fluidsynth' and source.suffix.lower() not in ('.mid', '.midi'): raise ValueError('A MIDI source is required')
    if app == 'epubcheck' and source.suffix.lower() != '.epub': raise ValueError('An EPUB is required')
    if app == 'typst' and source.suffix.lower() != '.typ': raise ValueError('A Typst source is required')
    if app == 'freecad':
        expected = '.py' if action == 'execute' else '.fcstd'
        if source.suffix.lower() != expected: raise ValueError('Expected source ' + expected)
        if action != 'execute' and output.suffix.lower() not in ({'.json'} if action == 'inspect' else {'.step', '.stp'}):
            raise ValueError('Expected JSON inspection or STEP export')
    extra = {}
    for name in ('resource_dir', 'font_dir', 'template', 'bibliography', 'csl', 'soundfont', 'audio'):
        if name in args:
            extra[name] = scoped(args[name], directory=name.endswith('_dir'))
    root = scoped(os.environ.get('RIGHAVEN_OUTPUT_DIR', str(output.parent)), exists=False, directory=True)
    root.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if directories: output.mkdir()
    work = folder(root, app + '-' + hashlib.sha256(str(output).encode()).hexdigest())
    result = {'output': str(output), 'original_preserved': True}
    original = digest(source) if source else None
    if app == 'ffmpeg':
        if action == 'probe':
            if output.suffix.lower() != '.json': raise ValueError('Probe output must be JSON')
            completed = capture(app, ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', source], output, root)
            info = json.loads(output.read_text())
            if not info.get('streams'): raise ValueError('No media streams found')
            # Full metadata remains in the JSON artifact; avoid flooding model
            # context with large tags or extradata from complex input containers.
            fields = {'index', 'codec_type', 'codec_name', 'width', 'height', 'pix_fmt', 'channels', 'sample_rate',
                      'r_frame_rate', 'avg_frame_rate', 'time_base', 'start_time', 'duration', 'nb_frames', 'bit_rate'}
            result['media'] = {'streams': [{k: v for k, v in row.items() if k in fields} for row in info['streams']],
                               'format': {k: v for k, v in info.get('format', {}).items() if k != 'tags'}}
        else:
            argv = ['ffmpeg', '-v', 'error', '-nostdin', '-n']
            if 'start' in args: argv += ['-ss', str(args['start'])]
            argv += ['-i', source]
            if action == 'extract_audio':
                if output.suffix.lower() != '.wav': raise ValueError('Decoded audio output must be WAV')
                argv += ['-vn', '-ac', str(args.get('channels', 2)), '-ar', str(args.get('sample_rate', 48000)), '-c:a', 'pcm_s16le']
            elif action == 'mux':
                if output.suffix.lower() not in ('.mp4', '.mov', '.mkv'): raise ValueError('Mux supports MP4/MOV/MKV')
                argv += ['-i', extra['audio'], '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac']
            else:
                if output.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm', '.wav', '.mp3', '.flac', '.ogg'): raise ValueError('Unsupported media export')
                if ('width' in args) != ('height' in args): raise ValueError('Width and height must be supplied together')
                if args.get('video_codec') == 'copy' and any(k in args for k in ('width', 'fps')): raise ValueError('Stream copy cannot resize or change FPS')
                for key, flag in (('video_codec', '-c:v'), ('audio_codec', '-c:a'), ('fps', '-r'), ('duration', '-t')):
                    if key in args: argv += [flag, str(args[key])]
                if 'width' in args: argv += ['-vf', f'scale={args["width"]}:{args["height"]}']
            argv += ['-threads', '2', output]
            completed = run(app, argv, root)
    elif app == 'playwright':
        env = {'NODE_PATH': INSTALL / 'toolkit/node_modules', 'righaven_JOB_OUTPUT': output,
               'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', str(INSTALL / 'playwright-browsers'))}
        if action == 'screenshot':
            argv = ['node', HERE / 'toolkit_browser.cjs', args['url'], output, args.get('width', 1280), args.get('height', 800)]
        elif action == 'execute':
            argv = ['node', source]
        else:
            # The generated config imports only the requested test, never every test
            # from another task. Trace/report data go to the explicit result folder.
            config = work / 'playwright.config.cjs'
            config.write_text('module.exports=' + json.dumps({'testDir': str(source.parent),
                'workers': 1, 'timeout': 60000, 'outputDir': str(output / 'test-results'),
                'reporter': [['json', {'outputFile': str(output / 'report.json')}]],
                'use': {'browserName': 'chromium', 'headless': True, 'trace': 'retain-on-failure',
                        'launchOptions': {'args': ['--no-sandbox', '--disable-dev-shm-usage']}}}) +
                ';\nmodule.exports.testMatch = new RegExp(' + json.dumps(r'(^|[/\\])' + re.escape(source.name) + '$') + ');\n')
            argv = ['node', INSTALL / 'toolkit/node_modules/playwright/cli.js', 'test', '--config', config]
        completed = run(app, argv, root, env=env)
    elif app == 'aubio':
        # Decode to a known analysis representation; timestamps are seconds of the
        # decoded source, not indices mistaken for seconds or beats claimed exact.
        decoded = work / 'analysis.wav'
        run(app, ['ffmpeg', '-v', 'error', '-y', '-i', source, '-vn', '-ac', '1', '-ar', '44100', '-c:a', 'pcm_s16le', decoded], root)
        argv = ['aubio', args['feature'], '-i', decoded, '-T', 'seconds']
        if args['feature'] == 'pitch': argv += ['-u', 'Hz']
        captured = work / ('native-' + uuid.uuid4().hex + '.txt')
        completed = capture(app, argv, captured, root)
        columns = {'onset': ['time_seconds'], 'beat': ['time_seconds'], 'tempo': ['tempo_bpm', 'native_qualifier'],
                   'pitch': ['time_seconds', 'pitch_hz'], 'notes': ['midi_note', 'onset_seconds', 'offset_seconds']}
        output.write_text(json.dumps({'feature': args['feature'], 'time_unit': None if args['feature'] == 'tempo' else 'seconds',
            'tempo_unit': 'bpm' if args['feature'] == 'tempo' else None, 'columns': columns[args['feature']],
            'pitch_unit': 'Hz' if args['feature'] == 'pitch' else None,
            'input_sha256': original, 'analysis_sample_rate': 44100,
            'rows': [line.split() for line in captured.read_text().splitlines() if line.strip()],
            'status': 'estimated', 'perceptual_review': 'not_run'}, indent=2))
    elif app == 'fluidsynth':
        bank = extra.get('soundfont', Path('/usr/share/sounds/sf2/TimGM6mb.sf2'))
        if not bank.is_file(): raise ValueError('SoundFont unavailable; supply a licensed local SF2')
        midi, sf2, wav = output / 'score.mid', output / 'bank.sf2', output / 'render.wav'
        shutil.copy2(source, midi); shutil.copy2(bank, sf2)
        rate, gain = args.get('sample_rate', 48000), args.get('gain', 0.6)
        argv = ['fluidsynth', '-ni', '-C', '0', '-R', '0', '-g', str(gain), '-r', str(rate),
                '-T', 'wav', '-O', 's16', '-F', wav, sf2, midi]
        completed = run(app, argv, root)
        (output / 'render-settings.json').write_text(json.dumps({'sample_rate': rate, 'gain': gain,
            'reverb': False, 'chorus': False, 'midi': 'score.mid', 'soundfont': 'bank.sf2',
            'soundfont_sha256': digest(sf2),
            'rebuild': f'fluidsynth -ni -C 0 -R 0 -g {gain} -r {rate} -T wav -O s16 -F rebuilt.wav bank.sf2 score.mid'}, indent=2))
        copyright = Path('/usr/share/doc/timgm6mb-soundfont/copyright')
        if 'soundfont' not in extra and copyright.is_file(): shutil.copy2(copyright, output / 'SOUNDFONT-LICENSE.txt')
        result.update(audio=str(wav), editable_sources=[str(midi), str(sf2), str(output / 'render-settings.json')],
                      soundfont_license='TimGM6mb: see SOUNDFONT-LICENSE.txt' if 'soundfont' not in extra else 'User-supplied bank: retain its redistribution license')
    elif app == 'epubcheck':
        completed = run(app, ['java', '-Xmx512m', '-jar', epub_jar(), source, '--json', output], root, allow_failure=True)
        # EPUBCheck returns 1 for conformance errors, not a successful validation.
        if not output.is_file(): raise RuntimeError('EPUBCheck did not create its JSON report: ' + completed.stderr[-2000:])
        report = json.loads(output.read_text())
        if completed.returncode not in (0, 1): raise RuntimeError('EPUBCheck execution failed: ' + completed.stderr[-2000:])
        result.update(status='passed' if completed.returncode == 0 else 'failed', report=report)
    elif app == 'pandoc':
        resource = extra.get('resource_dir', source.parent)
        argv = ['pandoc', source, '--output', output, '--resource-path', resource]
        for key, flag in (('from_format', '--from'), ('to_format', '--to')):
            if key in args: argv += [flag, args[key]]
        for key in ('template', 'bibliography', 'csl'):
            if key in extra: argv += ['--' + key, extra[key]]
        if args.get('standalone', True): argv.append('--standalone')
        completed = run(app, argv, root)
    elif app == 'typst':
        argv = ['typst', 'compile', '--root', extra.get('resource_dir', source.parent)]
        if 'font_dir' in extra: argv += ['--font-path', extra['font_dir']]
        argv += [source, output]
        completed = run(app, argv, root)
    elif app == 'freecad':
        completed = run(app, freecad_command(action, source, output), root,
                        env={'OMP_NUM_THREADS': '2'})
        if action == 'inspect':
            info = json.loads(output.read_text())
            result['inspection'] = {**info, 'objects': info['objects'][:200],
                                    'object_count': len(info['objects']), 'truncated': len(info['objects']) > 200}
    else:
        model = INSTALL / 'resources/whisper/ggml-tiny.bin'
        if not model.is_file(): raise RuntimeError('Pinned offline whisper model missing; rebuild the sandbox')
        decoded = output / 'analysis.wav'
        run(app, ['ffmpeg', '-v', 'error', '-i', source, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', decoded], root)
        argv = ['whisper-cli', '-m', model, '-f', decoded, '-l', args.get('language', 'auto'),
                '-t', '2', '-otxt', '-osrt', '-oj', '-of', output / 'transcript', '-np']
        completed = run(app, argv, root, env={'OMP_NUM_THREADS': '2'})
        if not all((output / ('transcript.' + ext)).is_file() for ext in ('txt', 'srt', 'json')):
            raise RuntimeError('Whisper did not create all requested transcription formats')
        transcript = (output / 'transcript.txt').read_text()
        result.update(transcript=transcript[:6000], transcript_truncated=len(transcript) > 6000,
                      files=[str(output / ('transcript.' + ext)) for ext in ('txt', 'srt', 'json')], perceptual_review='not_run')
    if not output.exists() or output.is_file() and not output.stat().st_size:
        raise RuntimeError('Native operation did not produce the requested file')
    if original and digest(source) != original:
        raise RuntimeError('Authoring script modified its original input')
    result['log'] = (completed.stdout + completed.stderr)[-4000:]
    # Receipts remain technical evidence under work/, not unsolicited downloads.
    (work / 'receipt.json').write_text(json.dumps({'app': app, 'operation': action, 'arguments': args,
        'input_sha256': original, 'returncode': completed.returncode, 'result': result}, ensure_ascii=False, indent=2))
    return result


def mcp(app):
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if 'id' not in request: continue
            method = request.get('method')
            if method == 'initialize':
                value = {'protocolVersion': request.get('params', {}).get('protocolVersion', '2024-11-05'),
                         'capabilities': {'tools': {}}, 'serverInfo': {'name': 'skill-' + app, 'version': '1.0'}}
            elif method == 'tools/list': value = {'tools': TOOLS[app]}
            elif method == 'ping': value = {}
            elif method == 'tools/call':
                params = request.get('params', {}); name = params.get('name', '')
                if not name.startswith(app + '.'): raise ValueError('Tool outside this adapter')
                result = invoke(app, name[len(app) + 1:], params.get('arguments', {}))
                value = {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}],
                         'structuredContent': result, 'isError': result.get('status') == 'failed'}
            else: raise ValueError('Unsupported MCP method')
            response = {'jsonrpc': '2.0', 'id': request['id'], 'result': value}
        except Exception as error:
            response = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                        'error': {'code': -32603, 'message': str(error)[:3000]}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


def main():
    inferred = Path(sys.argv[0]).name.removesuffix('-cli')
    if inferred == 'whisper-cpp': inferred = 'whisper'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', choices=list(TOOLS), default=inferred if inferred in TOOLS else None)
    parser.add_argument('--version', action='store_true')
    subs = parser.add_subparsers(dest='action')
    subs.add_parser('commands'); subs.add_parser('tools'); subs.add_parser('mcp')
    call = subs.add_parser('call'); call.add_argument('operation'); call.add_argument('arguments', help='JSON arguments; output must be a new workspace path')
    args = parser.parse_args()
    if not args.app: parser.error('Use an APP-cli symlink or --app APP')
    if args.version: native_version(args.app); return 0
    if args.action in ('commands','tools'): print(json.dumps({'tools': TOOLS[args.app]})); return 0
    if args.action == 'mcp': mcp(args.app); return 0
    if args.action == 'call':
        value = invoke(args.app, args.operation, json.loads(args.arguments))
        print(json.dumps(value, ensure_ascii=False)); return 2 if value.get('status') == 'failed' else 0
    parser.print_help(); return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr); sys.exit(1)
