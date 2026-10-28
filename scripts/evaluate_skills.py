#!/usr/bin/env python3
"""Opt-in DeepSeek skill evaluation. API key stays in the host environment.

Default: inspect plans for all catalog skills. --execute runs actual CLI tasks in
disposable offline Docker containers, without Codex/Gemini credentials.
This does not test RigHaven authentication or the production CLI engines.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'musescore': 'Componi una breve melodia in MusicXML, conserva MSCZ e MIDI, riapri la partitura ed esporta PDF e audio con il banco offline; non dichiarare ascolto senza prova.',
    'ifcopenshell': 'Crea un progetto BIM IFC4 con unità e struttura spaziale, conserva script e IFC, valida lo schema e distingui la verifica geometrica.',
    'manim': 'Crea una Scene esplicativa con tempi dichiarati, risorse relative e render Cairo CPU; sposta i sorgenti e ripeti il render.',
    'opentimelineio': 'Controlla i tempi e i media di una timeline OTIO esportata, produci OTIOD portabile e verifica la riapertura senza gli originali, senza duplicare FilmCraft.',
    'pymeshlab': 'Misura e ripara una mesh con filtro esplicito, confronta topologia prima/dopo e conserva originale, MLP, geometrie e MLX con risorse portabili.',
    'd2': 'Chiarisci un’idea con uno schema D2 leggibile, conserva i nodi e le relazioni, renderizza e rigenera da un sorgente trasferito.',
    'plantuml': 'Modella un’interazione UML con partecipanti e messaggi coerenti, conserva PUML autonomo e verifica il renderer nativo.',
    'mermaid': 'Prepara un diagramma Mermaid utile nella chat e in un documento, conserva MMD ed export verificati.',
    'excalidraw': 'Prepara una lavagna modificabile, conserva ID e relazioni, verifica che il JSON si riapra e che la modifica manuale resti possibile.',
    'bpmn': 'Modella un processo BPMN con eventi, task, responsabilità e DI, controlla riferimenti ed export senza avviare un motore workflow.',
    'structurizr': 'Descrivi un modello C4 con almeno una vista coerente, valida il DSL con le librerie mantenute ed esporta i sorgenti senza server o include remoti.',
    'ffmpeg': 'Verifica e converti media con codec e timeline espliciti, conservando i progetti di authoring e provando il sync sul prodotto finale.',
    'playwright': 'Collauda un percorso web reale a desktop/mobile: interazioni, stato salvato, errori, screenshot e test modificabili.',
    'aubio': 'Analizza attacchi e pitch di un audio fornito con unità esplicite, limiti e confronto con eventi osservabili.',
    'fluidsynth': 'Rendi un MIDI con SoundFont coerente, conserva MIDI e banca autorizzata, ricostruisci dopo trasferimento e verifica il WAV.',
    'epubcheck': 'Verifica indipendentemente un EPUB finale e correggi le risorse assenti nel sorgente senza confondere conformità e qualità.',
    'pandoc': 'Converti un documento strutturato mantenendo contenuto, citazioni e risorse; consegna sorgenti e ricetta collaudata.',
    'typst': 'Impagina un documento PDF da .typ con stili, immagini e font, controlla pagine e ricompila dopo trasferimento.',
    'freecad': 'Crea CAD parametrico .FCStd, verifica quote e solidi, modifica un parametro dopo riapertura ed esporta STEP.',
    'whisper': 'Trascrivi parlato fornito in TXT e SRT con modello CPU offline, controlla testo e origine dei timecode senza pretendere giudizi musicali.',
    'calibre': 'Converti un documento fornito in EPUB e PDF, conserva sorgenti modificabili e risorse, verifica metadati, ordine di lettura, struttura e trasferimento.',
    'blender': 'Crea una scena 3D con materiale, animazione a keyframe e render; consegna .blend riaperto con texture incorporate e GLB verificato.',
    'photocraft': 'Ritocca un’immagine con maschera mantenendo livelli modificabili; esporta PNG trasparente.',
    'vectorcraft': 'Prepara un logo SVG scalabile con testo modificabile e anteprime su chiaro e scuro.',
    'filmcraft': 'Monta due clip in un video 1920x1080, 25 fps, con audio sincronizzato e progetto editabile.',
    'lightcraft': 'Sviluppa 20 RAW in condizioni di luce diverse senza modificare originali e sidecar.',
    'pdfcraft': 'Unisci due PDF e oscura definitivamente un dato personale: verifica anche il testo estratto.',
    'effectcraft': 'Prepara un loop animato di 3 secondi a 25 fps con alpha e sorgente modificabile.',
    'designcraft': 'Impagina una brochure di 8 pagine da stampa con abbondanze e verifica PDF/X.',
    'gridcraft': 'Analizza un XLSX con date ambigue e mancanti; conserva formule e riconcilia i totali.',
    'wordcraft': 'Prepara una relazione DOCX con titoli, sommario, tabelle e PDF leggibile.',
    'deckcraft': 'Crea un PPTX di 6 slide da dati verificati da GridCraft, con grafici modificabili.',
    'cadcraft': 'Prepara DXF in millimetri con quote e verifica numerica delle misure e dei contorni.',
    'soundcraft': 'Prepara un mix stereo WAV, senza clipping, con misura di loudness e progetto multitraccia.',
    'figcraft': 'Progetta un flusso UI desktop/mobile con componenti, stati di errore e prototipo collegato.',
}
EXECUTION_CASES = {
    'calibre': 'Crea XHTML con due sezioni in italiano e un marcatore. Produci EPUB e PDF, verifica metadati e check nativo; estrai, modifica e ricostruisci i sorgenti su una copia. Consegna prodotto, sorgenti completi e rapporto. Dichiara la resa visiva non provata.',
    'gridcraft': 'Crea dati di prova con tre importi numerici 10, 20, 30. Produci un XLSX con formula di somma, riaprilo e verifica totale 60 con un controllo indipendente. Consegna XLSX e rapporto dei controlli.',
    'wordcraft': 'Crea una relazione breve in italiano con titolo e due paragrafi. Produci DOCX modificabile e PDF, riaprili e verifica testo e pagine. Puoi creare un TXT di input nella cartella assegnata. Dichiara la visione come non eseguita.',
    'soundcraft': 'Crea un breve audio dimostrativo usando la CLI installata e consegna sessione modificabile con dipendenze, WAV e rapporto. Verifica con ffprobe durata, codec, canali e sample rate; misura picchi se disponibile. Dichiara l’ascolto come non eseguito.',
}


def validate_plan(plan, agent):
    """Check routing and discovery, allowing a path or annotation for handoff.json."""
    if not isinstance(plan, dict) or plan.get('specialist') != agent:
        return False
    discovery = plan.get('discovery')
    if not isinstance(discovery, list) or not all(isinstance(item, str) for item in discovery):
        return False
    commands = '\n'.join(discovery)
    return (all(f'craft {cmd} {agent}' in commands for cmd in ('help', 'commands', 'tools'))
            and isinstance(plan.get('handoff'), str)
            and bool(re.search(r'(?<![\w.-])handoff\.json(?![\w.-])', plan['handoff']))
            and isinstance(plan.get('steps'), list) and bool(plan['steps'])
            and isinstance(plan.get('checks'), list) and bool(plan['checks']))


def request_api(key, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request('https://api.deepseek.com/' + path, data=body,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Never echo request headers or the key, even if a provider reflects it.
        detail = error.read().decode('utf-8', 'replace').replace(key, '[REDACTED]')[:500]
        raise RuntimeError(f'DeepSeek HTTP {error.code}: {detail}') from None


def docker(*args, timeout=90):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, errors='replace', timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-3000:])
    return result.stdout


def evaluate(key, model, agent, args, report_dir):
    common = (ROOT / 'skills/custom/skill-workspace/SKILL.md').read_text()
    skill = (ROOT / f'skills/custom/skill-{agent}/SKILL.md').read_text()
    system = (f'Sei lo specialista {agent} (ID di harness_delegate), con skill skill-{agent}. '
              'Segui queste procedure.\n' + common + '\n' + skill)
    task = CASES[agent]
    tools = None
    container = None
    output_dir = '/mnt/user-data/outputs/' + agent + '/evaluation'
    usage = []
    messages = []
    try:
        if args.execute:
            task = EXECUTION_CASES[agent]
            local_data = (args.resume / agent) if args.resume else (report_dir / agent)
            local_data.mkdir(mode=0o777, exist_ok=bool(args.resume))
            local_data.chmod(0o777)  # The managed Docker daemon remaps container UIDs.
            container = 'rh-eval-' + uuid.uuid4().hex[:12]
            docker('run', '-d', '--name', container, '--network=none', '--memory=1536m',
                   '--cpus=1.5', '--pids-limit=256', '--cap-drop=ALL',
                   '--security-opt=no-new-privileges', '--env', 'RIGHAVEN_OUTPUT_DIR=' + output_dir,
                   '--mount', f'type=bind,src={local_data},dst=/mnt/user-data',
                   '--mount', f'type=bind,src={ROOT / "scripts/craft.py"},dst=/opt/righaven/craft.py,readonly',
                   '--mount', f'type=bind,src={ROOT / "righaven/handoff.py"},dst=/review/handoff.py,readonly',
                   args.image, 'tail', '-f', '/dev/null')
            docker('exec', container, 'mkdir', '-p', output_dir + '/work', output_dir + '/previews')
            tools = [{'type': 'function', 'function': {'name': 'run_command',
                'description': 'Esegue un comando shell nella sandbox offline, senza credenziali. Timeout 60 secondi.',
                'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}]
            task += '\nEsegui realmente il lavoro con run_command. Non installare software. Non simulare risultati. '
            task += 'Salva tutto in ' + output_dir + ' e scrivi handoff.json secondo la skill comune. '
            task += 'La sandbox non ha accesso Internet. Nessuno strumento di visione/ascolto è disponibile. '
            task += 'Dopo un errore correggi il comando usando help/registro. Termina solo dopo la verifica dei file.'
            task += f' Hai un budget di {args.max_turns} turni: riserva gli ultimi tre alla consegna e al manifest.'
            if args.resume:
                task += (' Riprendi i file dell’esecuzione precedente già presenti nella cartella assegnata. '
                         'Leggi prima rapporti e risultati dei controlli, evita di ricreare output già validi '
                         'e completa handoff.json senza inventare verifiche.')
        else:
            task += ('\nQuesta è una prova di pianificazione senza file né strumenti: non eseguire né dichiarare controlli superati. '
                'Rispondi con un oggetto JSON avente esattamente queste sei chiavi al livello principale: '
                f'specialist (stringa letterale "{agent}"), discovery (lista di comandi craft help/commands/tools), '
                'steps (massimo 6 azioni specifiche), checks (massimo 6 controlli previsti), '
                'handoff (nome del file di consegna), limitations (lista). '
                'Usa i nomi reali dei tool solo dopo la scoperta; indica i controlli come previsti.')
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': task}]
        for turn in range(args.max_turns if args.execute else 1):
            if args.execute and turn == args.max_turns - 3:
                messages.append({'role': 'user', 'content':
                    'Restano tre turni: completa subito handoff.json con i file reali e le prove disponibili. '
                    'Indica not_run per i controlli non effettuati, senza ulteriori elaborazioni facoltative.'})
            payload = {'model': model, 'messages': messages, 'max_tokens': 5000}
            if tools:
                payload['tools'] = tools
            else:
                payload['response_format'] = {'type': 'json_object'}
            result = request_api(key, 'chat/completions', payload)
            usage.append(result.get('usage', {}))
            if result['choices'][0].get('finish_reason') == 'length':
                raise RuntimeError('Risposta troncata dal limite token; aumentare il budget o ridurre il caso')
            message = result['choices'][0]['message']
            messages.append(message)
            calls = message.get('tool_calls', [])
            if not calls:
                break
            for call in calls:
                try:
                    if call['function']['name'] != 'run_command':
                        raise ValueError('Tool sconosciuto')
                    command = json.loads(call['function']['arguments'])['command']
                    p = subprocess.run(['docker', 'exec', '-w', output_dir, container, 'bash', '-lc', command],
                                       capture_output=True, text=True, errors='replace', timeout=60)
                    if 'OCI runtime exec failed' in p.stdout + p.stderr or 'No space left on device' in p.stdout + p.stderr:
                        raise RuntimeError('Infrastruttura Docker non disponibile: ' + (p.stdout + p.stderr)[-1000:])
                    content = json.dumps({'returncode': p.returncode, 'stdout': p.stdout[-10000:], 'stderr': p.stderr[-3000:]})
                except (ValueError, KeyError, subprocess.TimeoutExpired) as error:
                    content = json.dumps({'error': str(error)})
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': content})
        if args.execute:
            code = ('import sys,json;sys.path.insert(0,"/review");from handoff import validate_handoff;'
                    f'print(json.dumps(validate_handoff({output_dir!r},"/mnt/user-data",require_delivery=True)))')
            handoff = json.loads(docker('exec', container, 'python3', '-c', code))
            passed = (not any(c['status'] == 'failed' for c in handoff['checks'])
                      and handoff['delivery']['source_status'] != 'unavailable'
                      and all(f['reopen']['status'] == 'passed' for f in handoff['delivery']['files']
                              if f['role'] in ('editable_source', 'source_archive')))
            details = {'handoff': handoff, 'quality_claims': 'Model-reported checks; file existence and paths verified by runtime.'}
        else:
            plan = json.loads(message['content'])
            passed = validate_plan(plan, agent)
            details = {'plan': plan, 'scope': 'Structure and discovery only; no CLI execution or semantic quality score.'}
        return {'agent': agent, 'passed': passed, 'skill_sha256': hashlib.sha256(skill.encode()).hexdigest(),
                'usage': usage, 'messages': messages, **details}
    except Exception as error:
        return {'agent': agent, 'passed': False, 'error': str(error).replace(key, '[REDACTED]'),
                'usage': usage, 'messages': messages}
    finally:
        if container:
            docker('rm', '-f', container)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--agents', nargs='+', choices=list(CASES))
    parser.add_argument('--model', default=os.getenv('DEEPSEEK_MODEL', ''))
    parser.add_argument('--max-turns', type=int, default=16)
    parser.add_argument('--resume', type=Path, help='Con --execute riutilizza i file sotto questa cartella di report precedente')
    parser.add_argument('--image', default=os.getenv('RIGHAVEN_SANDBOX_IMAGE', 'righaven-sandbox:0.1.0'),
                        help='Runtime dello stesso checkout; per una PR usare il digest sandbox del runtime-manifest')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports' / ('skills-' + uuid.uuid4().hex[:8]))
    args = parser.parse_args()
    key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not key:
        parser.error('Impostare DEEPSEEK_API_KEY nell’ambiente, senza salvarla nel repository')
    agents = args.agents or list(EXECUTION_CASES if args.execute else CASES)
    if args.execute and any(a not in EXECUTION_CASES for a in agents):
        parser.error('--execute supporta: ' + ', '.join(EXECUTION_CASES))
    if args.resume:
        args.resume = args.resume.resolve()
        if not args.execute or not all((args.resume / agent).is_dir() for agent in agents):
            parser.error('--resume richiede --execute e una cartella esistente per ogni specialista')
    if args.execute:
        # Multiple invocations must not duplicate the multi-GB VFS rootfs at once.
        (ROOT / 'reports').mkdir(exist_ok=True)
        execution_lock = (ROOT / 'reports/.execution.lock').open('a')
        try:
            fcntl.flock(execution_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Una valutazione Docker è già attiva in questo checkout; attendere la fine')
    model = args.model
    if not model:
        models = [item['id'] for item in request_api(key, 'models')['data']]
        model = next((m for m in ('deepseek-chat', 'deepseek-flash') if m in models), models[0])
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for agent in agents:
        result = evaluate(key, model, agent, args, args.output)
        results.append(result)
        report = {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'model': model, 'mode': 'execute' if args.execute else 'plan',
                  'resumed_from': str(args.resume) if args.resume else None,
                  'expected_cases': len(agents),
                  'passed': len(results) == len(agents) and all(r['passed'] for r in results),
                  'results': results}
        temporary = args.output / 'report.json.tmp'
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(args.output / 'report.json')
        print(('OK' if result['passed'] else 'FAIL'), agent, result.get('error', ''), flush=True)
        if 'DeepSeek HTTP' in result.get('error', ''):
            break
    return 0 if len(results) == len(agents) and all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
