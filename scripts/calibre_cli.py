#!/usr/bin/env python3
"""Headless Calibre CLI/MCP adapter: explicit local files, preserved inputs, supervised work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
try:
    from operations import supervise, folder
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from righaven.operations import supervise, folder

ROOT = Path(os.environ.get('RIGHAVEN_WORKSPACE_ROOT', '/mnt/user-data')).resolve()
TEXT = {'type': 'string'}
BOOLEAN = {'type': 'boolean'}
META = {k: TEXT for k in ('title', 'authors', 'language', 'publisher', 'tags')}
OPTIONS = {**META, 'cover': TEXT, 'extra_css': TEXT, 'chapter': TEXT, 'level1_toc': TEXT,
           'level2_toc': TEXT, 'epub_version': {'type': 'string', 'enum': ['2', '3']}}


def tool(name, description, fields, required):
    return {'name': 'calibre.' + name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': fields, 'required': required, 'additionalProperties': False}}


TOOLS = [
    tool('convert', 'Convert a local document without overwriting its source. Conversion is not editorial or visual approval.',
         {'input': TEXT, 'output': TEXT, **OPTIONS}, ['input', 'output']),
    tool('inspect', 'Reopen an EPUB/AZW3 and report native metadata, reading order and resources.', {'input': TEXT}, ['input']),
    tool('check', 'Run native Calibre structural checks; errors and warnings are distinct. Does not certify a reader or EPUBCheck.', {'input': TEXT}, ['input']),
    tool('metadata', 'Set metadata on a new copy, preserving the original document.', {'input': TEXT, 'output': TEXT, **META, 'cover': TEXT}, ['input', 'output']),
    tool('polish', 'Polish EPUB/AZW3 into a new file, without a conversion that rewrites the whole layout.',
         {'input': TEXT, 'output': TEXT, 'cover': TEXT, 'opf': TEXT,
          **{k: BOOLEAN for k in ('embed_fonts', 'subset_fonts', 'smarten_punctuation')}}, ['input', 'output']),
    tool('unpack', 'Export editable XHTML/CSS/OPF and resources using native calibre-debug. Use a new output directory.', {'input': TEXT, 'output': TEXT}, ['input', 'output']),
    tool('pack', 'Rebuild a previously unpacked publication; preserve its format and then run check.', {'source': TEXT, 'output': TEXT}, ['source', 'output']),
    tool('library', 'List, add or export books in a local workspace library. Never connects to a remote Calibre server.',
         {'library': TEXT, 'action': {'type': 'string', 'enum': ['list', 'add', 'export']}, 'input': TEXT, 'output': TEXT,
          'ids': {'type': 'array', 'items': {'type': 'integer'}, 'minItems': 1, 'maxItems': 100}}, ['library', 'action']),
]
BOOKS = {'.epub', '.azw3'}
FORMATS = {'.epub', '.azw3', '.pdf', '.docx', '.txt', '.htmlz', '.fb2', '.mobi', '.rtf'}


def scoped(value, *, exists=True, directory=False, fresh=False):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        raise ValueError('Percorso fuori dal workspace o link non ammesso: ' + str(value))
    path = path.resolve()
    if fresh and path.exists():
        raise ValueError('Non sovrascrivo file o cartelle esistenti: ' + str(value))
    if (exists or path.exists()) and not (path.is_dir() if directory else path.is_file()):
        raise ValueError('Input mancante: ' + str(value))
    return path


def safe_book(path):
    if path.suffix.lower() != '.epub':
        return
    with zipfile.ZipFile(path) as archive:
        size = 0
        if len(archive.infolist()) > 12000:
            raise ValueError('Pubblicazione troppo grande per il controllo')
        for item in archive.infolist():
            name = Path(item.filename)
            size += item.file_size
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16) or size > 512 * 1024 * 1024:
                raise ValueError('Risorsa non sicura o pubblicazione troppo grande')
        if archive.testzip():
            raise ValueError('Pubblicazione danneggiata: CRC non valido')


def environment():
    root = scoped(os.environ.get('RIGHAVEN_OUTPUT_DIR', str(ROOT)), exists=False, directory=True)
    root.mkdir(parents=True, exist_ok=True)
    for key, child in (('CALIBRE_CONFIG_DIRECTORY', 'config'), ('CALIBRE_TEMP_DIR', 'temp')):
        path = root / 'work/calibre' / child
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.environ[key] = str(path)
    # QtWebEngine needs a real QPA/OpenGL context even for non-GUI conversion.
    # The offscreen plugin can segfault during HTML/cover rendering; use Xvfb
    # with Mesa software OpenGL instead of probing unavailable GPU/Vulkan devices.
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    # ensure_app(headless=True) passes an explicit -platform argument, which
    # overrides QT_QPA_PLATFORM. Use Calibre's own switch for those subprocesses.
    os.environ['CALIBRE_HEADLESS_PLATFORM'] = 'xcb'
    os.environ.pop('QT_QUICK_BACKEND', None)
    os.environ['QT_OPENGL'] = 'software'
    os.environ['QSG_RHI_BACKEND'] = 'opengl'
    os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu --disable-gpu-compositing --disable-dev-shm-usage --disable-features=Vulkan'
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'  # Root inside the isolated worker container.
    return root


def run(argv, root, label):
    key = 'calibre-' + hashlib.sha256(json.dumps(argv).encode()).hexdigest()
    # The trusted structural helper uses the SDK's own CSS rules in Node and
    # never creates a WebEngine page. Conversion/rendering still needs Xvfb.
    structural=(len(argv)>=3 and Path(argv[0]).name=='calibre-debug' and argv[1]=='--exec-file'
                and Path(argv[2]).resolve()==Path(__file__).resolve().with_name('calibre_job.py'))
    command=argv
    if not structural:
        display = shutil.which('xvfb-run')
        if not display:
            raise RuntimeError('Rendering Calibre non disponibile: aggiorna l’immagine sandbox con xvfb-run e le librerie XCB.')
        command = [display, '--auto-servernum', '--server-args=-screen 0 1280x1024x24 -nolisten tcp', '--', *argv]
    completed, stats = supervise(command, root, key, timeout=1200, label='Calibre · ' + label)
    recovered = False
    if (completed.returncode in (-11,139) and not stats.get('oom_kills')
            and len(argv)>=3 and Path(argv[0]).name=='ebook-convert'):
        # A Qt renderer crash can leave a partial export. Never retry arbitrary
        # CLI errors, cancellations or OOM, and never replace a source document.
        source,target=scoped(argv[1]),scoped(argv[2],exists=False)
        if target==source or target.is_symlink():raise ValueError('Output di recupero non valido')
        if target.exists():target.unlink()
        recovery=folder(root,key+'-software-render')
        keys=('QT_QUICK_BACKEND','CALIBRE_CONFIG_DIRECTORY','CALIBRE_TEMP_DIR')
        previous={k:os.environ.get(k) for k in keys}
        try:
            os.environ['QT_QUICK_BACKEND']='software'
            for name,child in (('CALIBRE_CONFIG_DIRECTORY','config'),('CALIBRE_TEMP_DIR','temp')):
                path=recovery/child;path.mkdir(exist_ok=True);os.environ[name]=str(path)
            completed,stats=supervise(command,root,key+'-software-render',timeout=1200,
                label='Calibre · recupero rendering software')
            recovered=completed.returncode==0
        finally:
            for name,value in previous.items():
                if value is None:os.environ.pop(name,None)
                else:os.environ[name]=value
    if completed.returncode:
        cause = 'Memoria esaurita. ' if stats.get('oom_kills') else ''
        raise RuntimeError(cause + f'Calibre (exit {completed.returncode}): ' + (completed.stdout + completed.stderr)[-2500:])
    return completed.stdout+('\nRendering recuperato con backend software dopo un crash Qt; primo tentativo conservato nel registro.' if recovered else '')


def native_info(action, source, root):
    if source.suffix.lower() not in BOOKS:
        raise ValueError('Il controllo nativo del contenitore supporta EPUB e AZW3')
    safe_book(source)
    key = hashlib.sha256((action + str(source)).encode()).hexdigest()
    target = folder(root, 'calibre-info-' + key) / 'result.json'
    if target.exists():
        target.unlink()
    run(['calibre-debug', '--exec-file', str(Path(__file__).resolve().with_name('calibre_job.py')), '--',
         action, str(source), str(target)], root, 'Controllo struttura' if action == 'check' else 'Lettura metadati e struttura')
    value = json.loads(target.read_text())
    if not isinstance(value, dict) or not value.get('spine'):
        raise ValueError('Pubblicazione senza ordine di lettura valido')
    return value


def invoke(action, args):
    spec = next((t['inputSchema'] for t in TOOLS if t['name'] == 'calibre.' + action), None)
    if spec is None or not isinstance(args, dict) or set(args) - set(spec['properties']) or set(spec['required']) - set(args):
        raise ValueError('Operazione o argomenti Calibre non validi')
    for key, value in args.items():
        schema = spec['properties'][key]
        expected = {'string': str, 'boolean': bool, 'array': list}[schema['type']]
        if type(value) is not expected or 'enum' in schema and value not in schema['enum']:
            raise ValueError('Tipo o valore non valido: ' + key)
        if isinstance(value, str) and (not value.strip() or len(value) > 4000 or '\x00' in value):
            raise ValueError('Parametro vuoto o troppo grande: ' + key)
    if 'ids' in args and (not 1 <= len(args['ids']) <= 100 or any(type(n) is not int or n < 0 for n in args['ids'])):
        raise ValueError('ID della libreria non validi')
    source = scoped(args['input']) if 'input' in args else None
    if source:
        safe_book(source)
    output = scoped(args['output'], exists=False, fresh=True) if 'output' in args else None
    for name in ('cover', 'extra_css', 'opf'):
        if name in args:
            scoped(args[name])
    if action in ('convert', 'metadata', 'polish', 'pack') and output.suffix.lower() not in FORMATS:
        raise ValueError('Formato di output non esposto dall’adattatore: consulta i comandi nativi per altre capacità')
    if action in ('metadata', 'polish') and source.suffix.lower() != output.suffix.lower():
        raise ValueError('Metadati e polish conservano il formato; usa convert per cambiarlo')
    if action == 'polish' and source.suffix.lower() not in BOOKS:
        raise ValueError('Polish supportato per EPUB/AZW3')
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
    root = environment()
    if action in ('inspect', 'check'):
        return native_info(action, source, root)
    if action == 'convert':
        flags = [part for key, value in args.items() if key not in ('input', 'output')
                 for part in ('--' + key.replace('_', '-') + '=' + value,)]
        log = run(['ebook-convert', str(source), str(output), *flags], root, 'Conversione documento')
    elif action == 'metadata':
        shutil.copy2(source, output)
        flags = [part for key, value in args.items() if key not in ('input', 'output')
                 for part in ('--' + key.replace('_', '-') + '=' + value,)]
        log = run(['ebook-meta', str(output), *flags], root, 'Aggiornamento metadati')
    elif action == 'polish':
        flags = [part for key, value in args.items() if key in ('cover', 'opf') for part in ('--' + key + '=' + value,)]
        flags.extend('--' + key.replace('_', '-') for key, value in args.items() if type(value) is bool and value)
        if not flags:
            raise ValueError('Polish: specificare almeno una modifica')
        log = run(['ebook-polish', *flags, str(source), str(output)], root, 'Rifinitura della pubblicazione')
    elif action == 'unpack':
        if source.suffix.lower() not in BOOKS | {'.docx', '.htmlz'}:
            raise ValueError('Estrazione sorgenti supportata per EPUB/AZW3/DOCX/HTMLZ')
        log = run(['calibre-debug', '--explode-book', str(source), str(output)], root, 'Estrazione sorgenti modificabili')
        (output / '.righaven-source.json').write_text(json.dumps({'format': source.suffix.lower(),
            'original': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
    elif action == 'pack':
        source = scoped(args['source'], directory=True)
        marker = source / '.righaven-source.json'
        if not marker.is_file() or json.loads(marker.read_text()).get('format') != output.suffix.lower():
            raise ValueError('Usa sorgenti estratti con unpack e conserva il formato originale; convert cambia il formato')
        if any(p.is_symlink() for p in source.rglob('*')):
            raise ValueError('Sorgenti con link non ammessi')
        # Adapter provenance stays with editable sources, not as an unmanifested EPUB resource.
        with tempfile.TemporaryDirectory(prefix='pack-', dir=root / 'work/calibre') as staging:
            staged = Path(staging) / 'source'
            shutil.copytree(source, staged, ignore=shutil.ignore_patterns('.righaven-source.json'))
            log = run(['calibre-debug', '--implode-book', str(staged), str(output)], root, 'Ricostruzione dai sorgenti')
    else:
        library = scoped(args['library'], exists=False, directory=True)
        mode = args['action']
        if mode == 'add':
            if not source or output or 'ids' in args:
                raise ValueError('Library add richiede soltanto library, action e input')
            library.mkdir(parents=True, exist_ok=True)
            argv = ['calibredb', 'add', '--with-library', str(library), str(source)]
        elif mode == 'list':
            if source or output or 'ids' in args or not (library / 'metadata.db').is_file():
                raise ValueError('Library list richiede una libreria locale esistente')
            argv = ['calibredb', 'list', '--with-library', str(library), '--for-machine']
        else:
            if not output or source or not args.get('ids') or not (library / 'metadata.db').is_file():
                raise ValueError('Library export richiede output nuovo e ids espliciti')
            argv = ['calibredb', 'export', '--with-library', str(library), '--to-dir', str(output), ','.join(map(str, args['ids']))]
        log = run(argv, root, 'Libreria locale · ' + mode)
        if mode == 'export' and (not output.is_dir() or not any(p.is_file() for p in output.rglob('*'))):
            raise RuntimeError('La libreria non ha esportato file: verifica gli ID selezionati')
        return {'library': str(library), 'action': mode, 'result': json.loads(log) if mode == 'list' else log[-4000:]}
    if not output.exists() or output.is_file() and not output.stat().st_size:
        raise RuntimeError('Calibre non ha creato il risultato richiesto')
    result = {'output': str(output), 'log': log[-3000:], 'original_preserved': True}
    if output.is_file() and output.suffix.lower() in BOOKS:
        result['inspection'] = native_info('inspect', output, root)
    return result


def mcp():
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if 'id' not in request:
                continue
            method = request.get('method')
            if method == 'initialize':
                value = {'protocolVersion': request.get('params', {}).get('protocolVersion', '2024-11-05'),
                         'capabilities': {'tools': {}}, 'serverInfo': {'name': 'skill-calibre', 'version': '1.0'}}
            elif method == 'tools/list':
                value = {'tools': TOOLS}
            elif method == 'tools/call':
                params = request.get('params', {}); name = params.get('name', '')
                if not name.startswith('calibre.'):
                    raise ValueError('Tool Calibre sconosciuto')
                result = invoke(name.removeprefix('calibre.'), params.get('arguments', {}))
                value = {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}], 'structuredContent': result,
                         'isError': result.get('status') == 'failed'}
            elif method == 'ping':
                value = {}
            else:
                raise ValueError('Metodo MCP non supportato')
            response = {'jsonrpc': '2.0', 'id': request['id'], 'result': value}
        except Exception as error:
            response = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                        'error': {'code': -32603, 'message': str(error)[:3000]}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='store_true')
    subs = parser.add_subparsers(dest='action')
    for name in ('commands', 'mcp'):
        subs.add_parser(name)
    call = subs.add_parser('call'); call.add_argument('operation'); call.add_argument('arguments', help='JSON arguments for an exposed tool')
    for name in ('inspect', 'check'):
        sub = subs.add_parser(name); sub.add_argument('input')
    for name in ('convert', 'metadata', 'polish', 'unpack'):
        sub = subs.add_parser(name); sub.add_argument('input'); sub.add_argument('output')
        if name in ('convert', 'metadata'):
            for flag in OPTIONS if name == 'convert' else {**META, 'cover': TEXT}:
                sub.add_argument('--' + flag.replace('_', '-'))
        if name == 'polish':
            for flag in ('embed_fonts', 'subset_fonts', 'smarten_punctuation'):
                sub.add_argument('--' + flag.replace('_', '-'), action='store_true')
            for flag in ('cover', 'opf'):
                sub.add_argument('--' + flag)
    pack = subs.add_parser('pack'); pack.add_argument('source'); pack.add_argument('output')
    args = parser.parse_args()
    if args.version:
        return subprocess.run(['ebook-convert', '--version']).returncode
    if args.action == 'mcp':
        mcp(); return 0
    if args.action == 'commands':
        print(json.dumps({'tools': TOOLS, 'state': 'stateless files; library is an explicit local folder'})); return 0
    if args.action == 'call':
        value = invoke(args.operation, json.loads(args.arguments))
    elif args.action:
        value = invoke(args.action, {k: v for k, v in vars(args).items() if k not in ('action', 'version') and v is not None})
    else:
        parser.print_help(); return 0
    print(json.dumps(value, ensure_ascii=False))
    return 2 if value.get('status') == 'failed' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
