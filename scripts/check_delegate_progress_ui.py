#!/usr/bin/env python3
"""Real React+Tailwind browser acceptance: dock, previews, recovery and isolation.

Uses declared API fixtures and tiny genuine media, without accounts or an LLM.
The chat/composer layout mirrors the pinned upstream flex layout; integration
placement is checked separately against both real upstream pages.
"""
import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import subprocess
import tempfile
import threading

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-modules', type=Path, required=True)
    parser.add_argument('--screenshots-dir', type=Path)
    args = parser.parse_args()
    if args.screenshots_dir: args.screenshots_dir.mkdir(parents=True, exist_ok=True)
    modules = args.node_modules.resolve()
    repo = Path(__file__).resolve().parents[1]
    now = datetime.now(timezone.utc)
    iso = lambda t: t.isoformat()
    video_path = '/mnt/user-data/outputs/filmcraft/preview.mp4'
    job = {'job_id': 'rh-job-123456abcdef', 'agent': 'effectcraft', 'engine': 'codex',
        'model': 'fixture-model', 'can_stop': True, 'phase': 'running_tool', 'summary': 'Esporto il risultato con Effectcraft',
        'environment': {'id':'a'*64,'status':'ready','tools':['effectcraft','ffmpeg','soundcraft'],'assigned_tools':['effectcraft']},
        'egress': {'mode':'allowlist','domains':['api.openai.com','fonts.googleapis.com'],'refused':[{'destination':'cdn.example.net:443','attempts':2}]},
        'resources': {'memory_bytes': 1073741824, 'memory_limit_bytes': 2147483648, 'oom_kills': 0},
        'limits': {'cpus': 1.5}, 'operations': [{'id': 'render', 'state': 'running', 'label': 'Render finale', 'elapsed_seconds': 600, 'progress': {'done': 12, 'total': 48}}],
        'work_summary': 'Correggo inquadratura e proporzioni del robot prima del render',
        'created_at': iso(now - timedelta(minutes=18)), 'started_at': iso(now - timedelta(minutes=18)),
        'finished_at': '', 'deadline_at': iso(now + timedelta(minutes=7)),
        'last_activity_at': iso(now - timedelta(minutes=3)), 'heartbeat_at': iso(now),
        'files': [{'name': 'robot.ecproj', 'size': 120}], 'files_count': 1,
        'events': [{'at': iso(now - timedelta(minutes=18)), 'phase': 'planning', 'summary': 'Esporto il risultato con Effectcraft'}]}
    project = {'id': 'fixture-project', 'brief': 'Robot che balla', 'status': 'working',
        'outcome': {'title': 'Progetto dimostrativo', 'result': 'Video completo da presentare', 'format': 'MP4 e progetto modificabile', 'use': 'Presentazione', 'quality': 'Versione curata', 'constraints': [], 'assumptions': [], 'questions': []},
        'strategy': {'state': 'exploring', 'method': 'Composizione alternativa', 'reason': 'Il primo campione non rispetta i vincoli',
            'user_action': '', 'stop_reason': '', 'alternatives': [{'method': 'Costruzione da riferimenti', 'reason': 'Verificare prima gli elementi essenziali',
            'status': 'tested', 'tools': ['vectorcraft'], 'evidence': [{'path': '/mnt/user-data/outputs/review/report.json', 'sha256': 'fixture'}]}]},
        'method_recovery': {'message': 'Il metodo va rivalutato prima di richiedere risorse esterne'},
        'summary': 'Preparo una prima versione completa', 'next_action': 'Integro immagine, movimento e audio',
        'product_path': video_path, 'quality_status': 'not_reviewed',
        'acceptance': {'user_requests': ['Conserva il contenuto del riferimento fornito'],
            'request_documents': [{'path': '/mnt/user-data/.righaven-project/requests/original.txt'}],
            'request_manifest': {'path': '/mnt/user-data/.righaven-project/requests/index.json'}, 'request_count': 12, 'criteria': [
            {'id': 'request_fidelity', 'requirement': 'Contenuto conforme alla richiesta originale', 'critical': True}]},
        'review_criteria': [{'requirement_id':'request_fidelity','criterion':'Aspetto locale riuscito','status':'passed','method':'content','evidence':'Un solo aspetto è riuscito'}, {'requirement_id': 'request_fidelity', 'criterion': 'Conformità', 'method': 'content',
            'status': 'failed', 'evidence': 'Il contenuto è stato sostituito con una variante non richiesta.'}],
        'revision_actions': [{'requirement_id': 'request_fidelity', 'action': 'Correggere il contenuto usando il riferimento originale',
            'strategy': 'change_method', 'priority': 1}],
        'comparison': {'baseline_path': '/mnt/user-data/outputs/previous.txt', 'criteria': [
            {'requirement_id': 'request_fidelity', 'status': 'unchanged', 'evidence': 'Il difetto osservato è ancora presente'}]},
        'deliveries': [{'id': 'final', 'title': 'Robot con musica — versione 2', 'agent': 'filmcraft', 'at': iso(now),
                       'version':2, 'category':'version', 'current': True, 'technical_status': 'needs_revision', 'issues': ['Texture collegata mancante'], 'purpose': 'delivery'},
                      {'id': 'old', 'title': 'Prima prova muta', 'agent': 'effectcraft', 'at': iso(now-timedelta(hours=1)),
                       'current': False, 'technical_status': 'not_verified', 'issues': [], 'purpose': 'preview'}],
        'results': [{'path': video_path, 'label': 'preview.mp4', 'agent': 'filmcraft', 'validated': True, 'at': iso(now),
                     'delivery_id': 'final', 'role': 'export'},
                    {'path': '/mnt/user-data/outputs/filmcraft/Sorgenti.zip', 'label': 'Sorgenti.zip', 'agent': 'filmcraft', 'validated': True, 'at': iso(now),
                     'delivery_id': 'final', 'role': 'source_archive', 'open_with': 'Estrarre tutto, preparare i percorsi e aprire montaggio.locale.fcproj',
                     'editability': 'Timeline e clip separate'},
                    {'path': '/mnt/user-data/outputs/effectcraft/bozza.mp4', 'label': 'bozza.mp4', 'agent': 'effectcraft', 'validated': True, 'at': iso(now-timedelta(hours=1)),
                     'delivery_id': 'old', 'role': 'export'}],
        'steps': [{'id': 'visual', 'agent': 'photocraft', 'goal': 'Preparo immagini e texture', 'status': 'completed'},
                  {'id': 'motion', 'agent': 'effectcraft', 'goal': 'Animo il robot', 'status': 'running'},
                  {'id': 'audio', 'agent': 'soundcraft', 'goal': 'Verifico il mix recuperato', 'status': 'paused'},
                  {'id': 'final', 'agent': 'filmcraft', 'goal': 'Monto una prova con audio', 'status': 'pending'}]}
    state = {'job': job, 'project': project, 'unavailable': False}
    with tempfile.TemporaryDirectory(prefix='adaptive-harness-ui-') as directory:
        folder = Path(directory)
        (folder / 'fetch.ts').write_text('export const fetch = (...args: Parameters<typeof globalThis.fetch>) => globalThis.fetch(...args);')
        (folder / 'config.ts').write_text('export const getBackendBaseURL = () => "";')
        (folder / 'hooks.ts').write_text('export function useI18n(){return {locale:"it-IT"}}')
        (folder / 'entry.tsx').write_text('''import React from 'react';
import {createRoot} from 'react-dom/client';
import {DelegateProgress} from ''' + json.dumps(str(repo / 'frontend/delegate-progress.tsx')) + ''';
const root=createRoot(document.getElementById('root')!);
window.continued=0; window.failContinue=false;
window.showThread=(threadId='fixture',active=true,pending=true,error=false)=>root.render(<DelegateProgress threadId={threadId} active={active} pending={pending} coordinatorError={error} onPause={()=>{window.paused=(window.paused||0)+1}} onContinue={(message)=>{window.lastContinueMessage=message;window.continued++;if(window.failContinue)return Promise.reject(new Error("fixture submit unavailable"))}}/>);
window.showThread();
''')
        subprocess.run([str(modules / '.bin/esbuild'), str(folder / 'entry.tsx'), '--bundle', '--jsx=automatic',
            '--outfile=' + str(folder / 'app.js'), '--alias:react=' + str(modules / 'react'),
            '--alias:react-dom=' + str(modules / 'react-dom'), '--alias:@/core/api/fetcher=' + str(folder / 'fetch.ts'),
            '--alias:@/core/config=' + str(folder / 'config.ts'), '--alias:@/core/i18n/hooks=' + str(folder / 'hooks.ts'),
            '--alias:@/core/i18n/ui-text=' + str(repo / 'frontend/ui-text.ts')], check=True, capture_output=True)
        paragraphs = ''.join('<p class="mb-10">Messaggio storico %d: dettagli di una conversazione lunga.</p>' % i for i in range(100))
        (folder / 'index.html').write_text('''<!doctype html><html><meta name="viewport" content="width=device-width, initial-scale=1"><meta charset="utf-8"><link rel="stylesheet" href="/app.css">
<body><main class="mx-auto flex h-dvh max-w-[960px] flex-col"><header class="shrink-0 border-b p-3">Chat RigHaven</header><div id="messages" class="min-h-0 flex-1 overflow-y-auto p-3">'''+paragraphs+'''</div><footer class="shrink-0 p-3"><div id="root"></div><textarea class="h-14 w-full rounded border p-2" aria-label="Scrivi un messaggio"></textarea></footer></main><script src="/app.js"></script></body></html>''')
        css = '@import ' + json.dumps(str(modules / 'tailwindcss/index.css')) + ' source(none);\n'
        css += '@source ' + json.dumps(str(repo / 'frontend/delegate-progress.tsx')) + ';\n@source "./index.html";\n'
        css += '@source ' + json.dumps(str(repo / 'frontend/project-design.tsx')) + ';\n'
        css += '@source ' + json.dumps(str(repo / 'frontend/experience-panel.tsx')) + ';\n'
        css += '@source ' + json.dumps(str(repo / 'frontend/project-governance.tsx')) + ';\n'
        css += '@source ' + json.dumps(str(repo / 'frontend/project-guide.tsx')) + ';\n@source ' + json.dumps(str(repo / 'frontend/conversation-audit.tsx')) + ';\n'
        css += '@layer base { * { border-color: var(--color-border); } }\n'
        css += '@theme { --color-background: #ffffff; --color-foreground: #0f172a; --color-muted: #f1f5f9; --color-border: #cbd5e1; --color-ring: #2563eb; --color-muted-foreground: #64748b; }\n'
        (folder / 'input.css').write_text(css)
        subprocess.run([str(modules / '.bin/tailwindcss'), '-i', str(folder / 'input.css'), '-o', str(folder / 'app.css')],
                       check=True, capture_output=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '1', '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(folder / 'preview.mp4')], check=True, capture_output=True)

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
                if self.path.endswith('/harness-journey/decision'):
                    journey=state['journey'];stage=next(s for s in journey['stages'] if s['id']==data['stage_id'])
                    stage['status']={'approve':'approved','skip':'skipped','revise':'blocked'}[data['action']];journey['revision']+=1
                    journey['awaiting_owner']=[];journey['current']='design'
                    state['journey_decision']=data
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(json.dumps({'journey':journey}).encode());return
                if self.path.endswith('/stop'):
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(b'{"requested":true}');return
                if self.path.endswith('/harness-deliver-now'):
                    state['project']['user_control']={'deliver_now':True}
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(json.dumps({'user_control':state['project']['user_control']}).encode());return
                if self.path.endswith('/harness-experience/prefer'):
                    state['preferred_note'] = data['note']
                    self.do_GET(); return
                if self.path.endswith('/harness-experience/curate'):
                    state['curation_requested']=state.get('curation_requested',0)+1
                    state['pending_observations']=0
                    self.do_GET(); return
                valid = self.path == '/api/threads/fixture/harness-delivery/accept' and data.get('delivery_id') == 'final'
                if valid:
                    state['project'] = {**state['project'], 'status': 'ready', 'quality_status': 'accepted_by_user'}
                self.send_response(200 if valid else 409)
                self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({'project': state['project']}).encode())

            def do_PUT(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                if self.path.endswith('/harness-direction'):
                    state['project']['user_direction'] = {**body, 'revision': 1}
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                    self.wfile.write(b'{"running_step_ids":["motion"]}'); return
                if self.path.endswith('/harness-control'):
                    state['project']['user_control'] = body
                    if body['paused']:
                        state['job'] = {**state['job'], 'phase':'failed', 'resources_reclaimed':not state.get('defer_cleanup',False)}
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                    self.wfile.write(json.dumps({'user_control':body}).encode()); return
                if self.path.endswith('/harness-experience/lesson'):
                    if state.get('fail_accept'):
                        self.send_response(409);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{}');return
                    state['lesson_accepted'] = body['accepted']
                    self.do_GET(); return
                state['experience_excluded'] = body['excluded']
                self.do_GET()

            def do_GET(self):
                if '/harness-guide' in self.path:
                    if state.get('fail_guide'):
                        self.send_response(409); self.end_headers(); return
                    guide = {'title':'Progetto dimostrativo', 'result':'Montaggio finale modificabile', 'delivery_id':'final', 'is_current':True,
                        'technical_status':'passed', 'team':[{'title':'Montatore', 'goal':'Integrare i contributi'}],
                        'method':{'approach':'Animazione integrata con montaggio e audio', 'steps':['Riutilizzo dei sorgenti', 'Montaggio delle tracce'], 'scripts':[], 'limits':['Ascolto non effettuato']},
                        'methods':[{'id':'first','title':'Costruzione iniziale','actor':'Animatore','kind':'Campione','selected':False,'approach':'Curve e keyframe originali','steps':['Impostare il movimento']}], 'methods_omitted':0,
                        'instructions':{'overview':'Apri il progetto nativo', 'use':['Estrai tutte le risorse'],
                            'editing':[{'goal':'Cambiare una scena','files':['/mnt/user-data/outputs/filmcraft/Sorgenti.zip'], 'steps':['Apri la timeline', 'Modifica la clip'], 'check':'Controlla il nuovo render'}], 'limits':[]},
                        'components':[{'name':'Montaggio','tool':'filmcraft','version':'fixture','status':'passed'}],
                        'documents':[], 'files':[{'path':'/mnt/user-data/outputs/filmcraft/Sorgenti.zip','name':'Sorgenti.zip','role':'source_archive','open_with':'Estrarre tutto','editability':'Timeline e clip','limitations':[]}],
                        'reviews':[], 'limitations':[], 'unavailable_files':[], 'history_omitted':0,
                        'history':[{'id':'first','title':'Prima scena','actor':'Animatore','kind':'Campione','status':'completed','started_at':'2026-10-22T00:00:00Z','change':'first_export','detail':'','review_status':''},
                                   {'id':'copy','title':'Confezionamento','actor':'Montatore','kind':'Consegna','status':'completed','started_at':'2026-10-22T00:10:00Z','change':'identical_export','detail':'','review_status':''}]}
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(json.dumps(guide).encode()); return
                if self.path.endswith('/command.txt') or '/harness-job-file?path=' in self.path:
                    self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers()
                    self.wfile.write(b'modified command' if state.get('tamper_command') else b'python3 - <<"PY"\nrender_scene("sample.ecproj")\nverify_result()\nPY'); return
                if '/harness-audit' in self.path:
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                    self.wfile.write(json.dumps({'events':[{'seq':1,'at':'2026-10-22T00:00:00Z','actor':'Coordinatore','operation':'Strumento: read_file','status':'failed','detail':'Accesso non riuscito','correlation':'call-fixture','context':{'tool':'effectcraft-cli','action':'render','duration_seconds':1.25,'exit_code':1,'diagnostic':'Parametro CLI non riconosciuto','files':['/mnt/user-data/outputs/sample.ecproj'], 'command_preview':'python3 - <<"PY"\nrender_scene("sample.ecproj")', 'command_sha256':hashlib.sha256(b'python3 - <<"PY"\nrender_scene("sample.ecproj")\nverify_result()\nPY').hexdigest(), 'command_path':'/mnt/user-data/outputs/workspace/rh-job-123456abcdef/work/commands/aaaaaaaaaaaaaaaaaaaaaaaa/command.txt'}}], 'next_before':None,'latest_seq':1}).encode());return
                if '/harness-experience' in self.path:
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                    library = {'total':1,'excluded':int(state.get('experience_excluded',False)), 'pending':state.get('pending_observations',0), 'lessons':[{'id':'d'*64,'accepted':state.get('lesson_accepted',False),'excluded':False, 'basis':{'source_ids':['a'*64], 'source_statuses':['failed'], 'lesson':{'title':'Riaprire i pacchetti in una cartella nuova','applies_when':'Quando il progetto contiene risorse collegate','procedure':['Estrarre tutto il pacchetto'],'verification':['Verificare i collegamenti'],'limits':'Non prova qualità estetica','tools':['filmcraft']}}}], 'observations':[{
                        'id':'a'*64,'at':'2026-10-20T00:00:00Z','excluded':state.get('experience_excluded',False),
                        'observation':{'criterion':state.get('preferred_note','Risorse portabili'),'status':'preferred_by_user' if state.get('preferred_note') else 'failed','method':'functional','evidence':'Risorsa collegata mancante',
                        'corrections':['Includere tutte le risorse'],'tools':{'filmcraft':'fixture'},'product_sha256':'b'*64,'report_sha256':'c'*64}}]}
                    if state.get('long_lesson'):
                        record=library['lessons'][0]
                        record['basis']['impact']={'level':'major','basis':'observed','reason':'Beneficio documentato con evidenze. '*20+'FINE BENEFICIO COMPLETO'}
                        record['basis']['lesson'].update(
                            applies_when='Condizioni di applicazione. '*12,
                            procedure=['Passaggio '+str(i)+': '+'Descrizione operativa leggibile. '*8 for i in range(12)],
                            verification=['Controllare una risorsa e una variante. '*6,'ULTIMA VERIFICA LEGGIBILE'],
                            limits='Limiti e condizioni da conservare. '*8+'LIMITE FINALE LEGGIBILE')
                        record['basis']['lesson']['procedure'][5]+=' https://example.test/'+('risorsa'*35)
                    if state.get('many_lessons'):
                        template = library['lessons'][0]
                        library['lessons'] = [{**template,'id':str(i)*64,'accepted':False,
                            'basis':{**template['basis'],'impact':{'level':level,'basis':basis,'reason':'Prova dichiarata per il collaudo'},
                                'lesson':{**template['basis']['lesson'],'title':title}}}
                            for i,(title,level,basis) in enumerate([
                                ('Piccolo perfezionamento','minor','observed'),
                                ('Evita consegna inutilizzabile','major','observed'),
                                ('Beneficio da confermare','major','hypothesis'),
                                ('Riduzione tempi registrata','major','measured'),
                                ('Impatto non valutato','unknown','hypothesis')])]
                    if state.get('technical_lessons'):
                        template = library['lessons'][0]
                        library['lessons'] += [{**template, 'id': str(i) * 64,
                            'category': 'tool_operation', 'approval': 'automatic' if active else 'pending',
                            'accepted': active, 'basis': {**template['basis'],
                                'lesson': {**template['basis']['lesson'], 'title': title}}}
                            for i, (title, active) in enumerate([
                                ('Keyframe persistenti verificati', True), ('Parametro senza prova', False)], start=7)]
                    library['current_project']={'observations':1,'pending':state.get('pending_observations',0),
                        'meaningful':state.get('current_pending',state.get('pending_observations',0)),
                        'lessons':len(library['lessons']),'lesson_ids':[] if state.get('foreign_lessons_only') else [r['id'] for r in library['lessons']]}
                    for record in library['observations']:record['observation']['source_thread']='fixture'
                    if state.get('curation_requested'):library['curation']={'status':'completed','message':'Una lezione salvata senza modificare il progetto.'}
                    self.wfile.write(json.dumps(library).encode()); return
                if self.path.endswith('/harness-journey'):
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(json.dumps({'journey':state.get('journey') if '/fixture/' in self.path else None}).encode());return
                if self.path.endswith('/harness-jobs'):
                    self.send_response(503 if state['unavailable'] else 200)
                    self.send_header('Content-Type', 'application/json'); self.end_headers()
                    owned = '/fixture/' in self.path
                    try:
                        reported_job = {**state['job'], 'heartbeat_at': iso(datetime.now(timezone.utc))}
                        self.wfile.write(json.dumps({'jobs': ([reported_job,*state.get('extra_jobs',[])]) if owned else [],
                            'project': state['project'] if owned else None}).encode())
                    except (BrokenPipeError, ConnectionResetError):
                        pass  # Navigation deliberately aborts the previous request.
                elif '/artifacts/' in self.path:
                    self.send_response(200); self.send_header('Content-Type', 'video/mp4'); self.end_headers()
                    self.wfile.write((folder / 'preview.mp4').read_bytes())
                else:
                    super().do_GET()

        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=directory))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1100, 'height': 800})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                dock = page.get_by_test_id('delegate-progress')
                expect(page.get_by_test_id('harness-status')).to_have_text('Avanzamento da verificare')
                expect(page.get_by_test_id('harness-summary')).to_have_text('Render finale · 12/48 campioni')
                expect(page.get_by_test_id('harness-health')).to_contain_text('Nessun nuovo avanzamento')
                expect(page.get_by_test_id('delegate-job')).to_have_count(0)  # no wall of technical detail
                def section(name):
                    # Deliveries are listed as versions; the team section includes its activities.
                    name = {'Consegne': 'Versioni', 'Attività': 'Squadra'}.get(name, name)
                    if not page.get_by_test_id('harness-drawer').count():
                        page.get_by_role('button', name='Dettagli progetto', exact=True).click()
                    page.get_by_test_id('harness-drawer').get_by_role('navigation').get_by_role('button', name=name, exact=True).click()
                section('Registro')
                expect(page.get_by_test_id('conversation-audit')).to_be_visible()
                expect(page.get_by_test_id('conversation-audit').get_by_text('Coordinatore',exact=True)).to_be_visible()
                expect(page.get_by_test_id('conversation-audit').get_by_role('link',name='Scarica CSV')).to_have_attribute('href','/api/threads/fixture/harness-audit?export=true')
                page.get_by_test_id('conversation-audit').get_by_text('Dettagli operazione',exact=True).click()
                expect(page.get_by_test_id('operation-details')).to_contain_text('1.25 s')
                expect(page.get_by_test_id('operation-details')).to_contain_text('Parametro CLI non riconosciuto')
                expect(page.get_by_test_id('operation-details')).to_contain_text('sample.ecproj')
                expect(page.get_by_test_id('operation-command')).to_contain_text('render_scene')
                page.get_by_text('Apri comando completo / script inline',exact=True).click()
                expect(page.get_by_test_id('operation-command')).to_contain_text('verify_result()')
                state['tamper_command'] = True
                page.get_by_text('Apri comando completo / script inline',exact=True).click()
                page.get_by_text('Apri comando completo / script inline',exact=True).click()
                expect(page.get_by_test_id('operation-command')).to_contain_text('Testo non disponibile')
                expect(page.get_by_test_id('operation-command')).not_to_contain_text('modified command')
                state['tamper_command'] = False
                page.get_by_text('Apri comando completo / script inline',exact=True).click()
                page.get_by_text('Apri comando completo / script inline',exact=True).click()
                expect(page.get_by_test_id('operation-command')).to_contain_text('verify_result()')
                page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                composer = page.get_by_role('textbox', name='Scrivi un messaggio')
                for viewport in ({'width': 1100, 'height': 800}, {'width': 390, 'height': 740}):
                    page.set_viewport_size(viewport)
                    for offset in (0, 20000):
                        page.locator('#messages').evaluate('(el, offset)=>el.scrollTop=offset', offset)
                        box, input_box = dock.bounding_box(), composer.bounding_box()
                        assert box['y'] >= 0 and box['y'] + box['height'] <= input_box['y'] + 1
                        assert input_box['y'] + input_box['height'] <= viewport['height']
                    page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$')).click()
                    expect(page.get_by_text('Bozza di lavoro:', exact=False)).to_be_visible()
                    page.wait_for_function('document.querySelector("[data-testid=harness-drawer]").getBoundingClientRect().top >= 0')
                    drawer = page.get_by_test_id('harness-drawer').bounding_box()
                    assert drawer['y'] >= 0 and drawer['y'] + drawer['height'] <= viewport['height']
                    assert page.get_by_test_id('harness-drawer').evaluate('(el)=>el.matches(":modal")')
                    expect(page.get_by_role('button', name='Chiudi dettagli del progetto')).to_be_in_viewport()
                    composer.evaluate('(el)=>el.style.height="140px"')
                    page.wait_for_function('document.querySelector("[data-testid=harness-drawer]").getBoundingClientRect().top >= 0')
                    expect(page.get_by_role('button', name='Chiudi dettagli del progetto')).to_be_in_viewport()
                    composer.evaluate('(el)=>el.style.height=""')
                    section('Registro')
                    expect(page.get_by_test_id('conversation-audit')).to_be_visible()
                    page.get_by_label('Solo errori e interruzioni').check()
                    expect(page.get_by_test_id('conversation-audit').get_by_text('Strumento: read_file')).to_be_visible()
                    if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir/f'registro-{viewport["width"]}.png'))
                    section('Risultato')
                    expect(page.get_by_test_id('paired-sources').get_by_role('link', name='Sorgenti.zip')).to_be_visible()
                    expect(page.get_by_test_id('paired-sources').get_by_role('link', name='bozza.mp4')).to_have_count(0)
                    guide = page.get_by_test_id('project-guide')
                    guide.locator('summary').first.click()
                    expect(guide).to_contain_text('Montaggio finale modificabile')
                    expect(guide).to_contain_text('Cambiare una scena')
                    expect(page.get_by_test_id('delivery-download').get_by_role('link',name='Scarica file e guida')).to_have_attribute('href','/api/threads/fixture/harness-guide?delivery_id=final&format=zip')
                    guide.get_by_text('Storia delle lavorazioni',exact=True).click()
                    expect(guide).to_contain_text('Export identico al precedente')
                    guide.get_by_text('Dalla prima costruzione alle revisioni: procedure registrate',exact=True).click()
                    expect(guide).to_contain_text('Curve e keyframe originali')
                    if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir / f'guida-{viewport["width"]}.png'))
                    guide.locator('summary').first.click()
                    assert page.get_by_test_id('primary-result').evaluate('(el)=>!!(el.compareDocumentPosition(document.querySelector("[data-testid=acceptance-criteria]")) & Node.DOCUMENT_POSITION_FOLLOWING)')
                    video = page.get_by_label('Anteprima video')
                    video.evaluate('(v)=>v.play()')
                    page.wait_for_function('document.querySelector("video").currentTime > .1')
                    video.evaluate('(v)=>v.pause()')
                    page.get_by_test_id('rh-drawer-content').evaluate('(el)=>el.scrollTop=el.scrollHeight')
                    expect(page.get_by_role('button', name='Chiudi dettagli del progetto')).to_be_in_viewport()
                    if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir/f'risultato-{viewport["width"]}.png'))
                    page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                state['defer_cleanup'] = True
                page.get_by_role('button', name='Intervieni', exact=True).click()
                direction = page.get_by_test_id('project-direction')
                direction.get_by_label('Tecnica visiva, se pertinente').select_option('vector')
                direction.get_by_label('Indicazioni per questo progetto').fill('Disegni modificabili, senza raster incorporati')
                if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir/'intervento-mobile.png'))
                page.get_by_role('button', name='Applica e riprendi').click()
                page.wait_for_timeout(1500)
                assert page.evaluate('window.continued') == 0, 'Must wait for actual worker cleanup'
                assert state['project']['user_control']['paused'] is True
                state['job']['resources_reclaimed'] = True
                state['defer_cleanup'] = False
                expect(page.get_by_test_id('harness-drawer')).to_have_count(0)
                assert page.evaluate('window.paused') == 1
                assert page.evaluate('window.continued') == 1
                page.evaluate('window.continued=0')
                assert state['project']['user_control']['paused'] is False
                assert state['project']['user_direction']['visual_approach'] == 'vector'
                state['job'] = job
                section('Lezioni')
                if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir/'lezioni-mobile.png'))
                experience_panel = page.get_by_test_id('experience-panel')
                expect(experience_panel).to_contain_text('Proposta: non ancora usata nelle skills')
                state['fail_accept'] = True
                experience_panel.get_by_role('button',name='Accetta questa lezione',exact=True).click()
                expect(experience_panel.get_by_role('alert')).to_be_visible()
                expect(experience_panel).to_contain_text('Proposta: non ancora usata nelle skills')
                state['fail_accept'] = False
                experience_panel.get_by_role('button',name='Accetta questa lezione',exact=True).click()
                expect(experience_panel).to_contain_text('Accettata per il riutilizzo')
                experience_panel.get_by_test_id('accepted-lessons').locator('summary').first.click()
                experience_panel.get_by_role('button',name='Rimuovi dalle skills',exact=True).click()
                expect(experience_panel).to_contain_text('Proposta: non ancora usata nelle skills')
                experience_panel.get_by_text('Fonti e preferenze · questo progetto (1)', exact=True).click()
                expect(experience_panel).to_contain_text('Risorsa collegata mancante')
                expect(page.get_by_role('button', name='Escludi dal riutilizzo', exact=True)).to_have_count(0)
                page.get_by_label('Cosa vuoi riutilizzare?').fill('Cambiare metodo dopo il campione e verificare due scene')
                page.get_by_role('button',name='Conserva questo metodo',exact=True).click()
                expect(experience_panel).to_contain_text('Metodo preferito dall’utente')
                # Read a complete long lesson in one scrollable view, including
                # the impact text formerly lost behind the two-line clamp.
                state['long_lesson'] = True
                for reader_viewport in ({'width':1100,'height':800},{'width':390,'height':740}):
                    page.set_viewport_size(reader_viewport)
                    page.reload(); section('Lezioni')
                    before_read=page.evaluate('window.continued')
                    page.get_by_test_id('read-lesson').first.click()
                    reader=page.get_by_test_id('lesson-reader')
                    expect(reader).to_be_visible()
                    expect(reader.get_by_test_id('lesson-full-impact')).to_contain_text('FINE BENEFICIO COMPLETO')
                    expect(reader).to_contain_text('ULTIMA VERIFICA LEGGIBILE')
                    expect(page.get_by_role('navigation',name='Sezioni del progetto')).to_have_count(0)
                    expect(page.get_by_test_id('harness-drawer').locator('footer')).to_have_count(0)
                    limits=reader.get_by_test_id('lesson-full-limits')
                    limits.scroll_into_view_if_needed()
                    expect(limits).to_contain_text('LIMITE FINALE LEGGIBILE')
                    assert page.evaluate('window.continued')==before_read,'Reading must never start a coordinator run'
                    metrics=reader.evaluate('e=>{const s=e.closest("[data-testid=rh-drawer-content]"),p=e.querySelector("[data-testid=lesson-full-limits]");return {scroll:s.scrollWidth,width:s.clientWidth,bottom:p.getBoundingClientRect().bottom,visible:s.getBoundingClientRect().bottom}}')
                    assert metrics['scroll']<=metrics['width']+1, metrics
                    assert metrics['bottom']<=metrics['visible']+1, metrics
                    if args.screenshots_dir:page.screenshot(path=str(args.screenshots_dir/('lezione-completa-'+str(page.viewport_size['width'])+'.png')))
                    reader.get_by_role('button',name='← Torna alle lezioni',exact=True).click()
                    expect(page.get_by_test_id('experience-panel')).to_be_visible()
                    expect(page.get_by_role('navigation',name='Sezioni del progetto')).to_be_visible()
                state['long_lesson']=False
                state['many_lessons'] = True
                page.reload(); section('Lezioni')
                visible_lessons = page.locator('[data-testid=general-lesson]:visible')
                expect(visible_lessons).to_have_count(3)
                expect(visible_lessons.nth(0)).to_contain_text('Riduzione tempi registrata')
                expect(visible_lessons.nth(1)).to_contain_text('Evita consegna inutilizzabile')
                expect(visible_lessons.nth(2)).to_contain_text('Piccolo perfezionamento')
                page.get_by_text('Altre proposte (2)',exact=True).click()
                expect(page.locator('[data-testid=general-lesson]:visible')).to_have_count(5)
                if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir/'lezioni-impatto.png'))
                state['many_lessons'] = False
                page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                state['technical_lessons'] = True
                section('Lezioni')
                experience_panel = page.get_by_test_id('experience-panel')
                expect(experience_panel).to_contain_text('1 metodi da valutare · 0 metodi accettati · 1 conoscenze tecniche attive')
                expect(page.locator('[data-testid=general-lesson]:visible')).to_have_count(1)
                page.get_by_test_id('technical-lessons').locator('summary').first.click()
                technical = page.get_by_test_id('technical-lessons')
                expect(technical).to_contain_text('Tecnica attivata automaticamente dopo il test')
                expect(technical).to_contain_text('In attesa di verifica tecnica automatica')
                expect(technical.get_by_role('button', name='Accetta questa lezione')).to_have_count(0)
                expect(technical.get_by_role('button', name='Rimuovi dalle skills')).to_have_count(1)
                state['technical_lessons'] = False
                page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                section('Attività')
                expect(page.get_by_test_id('operation-progress')).to_contain_text('12/48 campioni osservati')
                page.get_by_text('Modello e risorse', exact=True).click()
                expect(page.get_by_text('RAM osservata: 1024 MiB · limite 2048 MiB')).to_be_visible()
                expect(page.get_by_text('CPU: massimo 1.5 core assegnati; non è il consumo istantaneo.')).to_be_visible()
                expect(page.get_by_test_id('job-environment')).to_contain_text('Strumenti assegnati: Effectcraft.')
                page.get_by_text('Programmi presenti nell’ambiente (3)',exact=True).click()
                expect(page.get_by_test_id('job-environment')).to_contain_text('Effectcraft, Ffmpeg, Soundcraft')
                expect(page.get_by_test_id('job-egress')).to_contain_text('Rete limitata a api.openai.com, fonts.googleapis.com. Connessioni bloccate: cdn.example.net:443 ×2.')
                page.get_by_role('button',name='Interrompi questa fase',exact=True).click()
                expect(page.get_by_role('button',name='Arresto richiesto…',exact=True)).to_be_disabled()
                page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                # A professional role is compiled from the project, independently of CLI names.
                state['job'] = {**job, 'role_id': 'coherence', 'role_title': 'Responsabile della coerenza', 'role_version': 'abcdef0123456789'}
                state['project'] = {**project, 'roles': [{'id': 'coherence', 'title': 'Responsabile della coerenza',
                    'mission': 'Confrontare risultati e vincoli', 'capability_rationale':'Confronto i modelli sorgenti con il brief; la conversione del formato non sostituisce il modello.', 'expertise': ['Analisi delle dipendenze'],
                    'checks': ['Confrontare il risultato con il brief integrale'], 'tools': [], 'skill_bindings':[{'name':'skill-problem-solving','revision':'a'*64}], 'version': 'abcdef0123456789'},
                    {'id': 'verify', 'title': 'Revisore indipendente', 'mission': 'Verificare la consegna', 'expertise': ['Verifiche indipendenti'], 'checks': ['Raccogliere evidenze'], 'tools': [], 'version': 'fedcba0123456789'}],
                    'steps': [{**step, 'role_id': 'coherence' if step['id'] == 'motion' else 'verify' if step['id'] == 'final' else '', 'attempt_count': 1 if step['id'] == 'motion' else 0} for step in project['steps']]}
                page.reload()
                expect(page.get_by_test_id('harness-status')).to_have_text('Avanzamento da verificare')
                section('Squadra')
                compiled = page.get_by_test_id('compiled-role').first
                expect(compiled).to_contain_text('Al lavoro')
                expect(compiled).to_contain_text('Analisi delle dipendenze')
                compiled.get_by_text('Perché questi strumenti',exact=True).click()
                expect(compiled).to_contain_text('la conversione del formato non sostituisce il modello.')
                expect(compiled.get_by_test_id('role-method-skills')).to_contain_text('problem-solving')
                expect(compiled.get_by_test_id('role-method-skills')).not_to_contain_text('aaaaaaaa')
                expect(page.get_by_test_id('compiled-role').nth(1)).to_contain_text('Previsto')
                compiled.get_by_text('Metodo e verifiche previste',exact=True).click()
                expect(compiled).to_contain_text('Strumenti di base del progetto')
                expect(compiled).to_contain_text('Confrontare il risultato con il brief integrale')
                compiled.get_by_text('Dettagli tecnici delle istruzioni',exact=True).click()
                expect(compiled).to_contain_text('Impronta del ruolo: abcdef0123456789')
                expect(compiled).to_contain_text('Non indicano il livello di competenza')
                state['job'] = job
                section('Stato')
                overview = page.get_by_test_id('project-overview')
                expect(overview).to_contain_text('Video completo da presentare')
                expect(overview).to_contain_text('MP4 e progetto modificabile')
                expect(overview).to_contain_text('1 di 4 incarichi conclusi')
                expect(overview).to_contain_text('Responsabilità attuale:')
                page.get_by_test_id('project-method').locator('summary').click()
                expect(page.get_by_test_id('project-method')).to_contain_text('Composizione alternativa')
                expect(page.get_by_test_id('project-method')).to_contain_text('Prova disponibile')
                expect(page.get_by_test_id('project-method')).to_contain_text('prima di richiedere risorse esterne')
                expect(page.get_by_test_id('project-method').get_by_role('link', name='Prova 1')).to_have_attribute('href', '/api/threads/fixture/artifacts/mnt/user-data/outputs/review/report.json')
                expect(page.get_by_test_id('revision-actions')).to_contain_text('Correggere il contenuto usando il riferimento originale')
                expect(page.get_by_test_id('revision-actions')).to_contain_text('Serve provare un metodo diverso')
                expect(page.get_by_test_id('quality-comparison')).to_contain_text('Invariato')
                expect(page.get_by_test_id('quality-comparison')).to_contain_text('Il difetto osservato è ancora presente')
                page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                expect(page.get_by_test_id('project-identity')).to_contain_text('Progetto dimostrativo')
                # A change of live roles must not mix old context into today's remaining work.
                state['project'] = {**state['project'], 'orientation': {'active_step_ids': ['motion', 'final'],
                    'history_step_ids': ['visual', 'audio'], 'history_count': 2},
                    'steps': [{**step, 'role_id': 'retired' if step['id'] in ('visual', 'audio') else step.get('role_id', '')} for step in state['project']['steps']]}
                page.reload()
                section('Stato')
                expect(page.get_by_test_id('project-position')).to_contain_text('0 di 2 incarichi conclusi')
                expect(page.get_by_test_id('project-history')).to_contain_text('Altre attività del progetto (2)')
                page.get_by_test_id('project-history').locator('summary').click()
                expect(page.get_by_test_id('project-history')).to_contain_text('Verifico il mix recuperato')
                section('Squadra')
                expect(page.get_by_test_id('team-plan')).not_to_contain_text('Verifico il mix recuperato')
                state['project'] = {**project, 'status': 'clarifying', 'outcome': {**project['outcome'], 'format': '', 'questions': ['Una proposta di lavoro o un prodotto pronto da distribuire?']}}
                state['job'] = {**job, 'phase': 'completed', 'finished_at': iso(now), 'resources_reclaimed': True, 'cleanup_finished_at': iso(now)}
                page.reload()
                page.evaluate("window.showThread('fixture',false,false,false)")
                expect(page.get_by_test_id('harness-status')).to_have_text('Definiamo il risultato insieme')
                expect(page.get_by_role('button', name='Riprendi lavoro')).to_have_count(0)
                section('Stato')
                expect(page.get_by_test_id('brief-questions')).to_contain_text('Una proposta di lavoro o un prodotto pronto da distribuire?')
                expect(page.get_by_test_id('project-overview')).to_contain_text('Da definire con te')
                section('Attività')
                expect(page.get_by_test_id('worker-reclaimed')).to_contain_text('Risorse della fase liberate')
                state['job'] = job
                page.evaluate("window.showThread('fixture',true,true,false)")
                # A report-only inventory must never replace the selected artifact.
                state['project'] = {**project, 'results': [{'path': '/mnt/user-data/outputs/review/report.json',
                    'label': 'report.json', 'agent': 'filmcraft', 'validated': True, 'at': iso(now)}]}
                page.reload()
                page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$')).click()
                expect(page.get_by_label('Anteprima video')).to_have_attribute('src', '/api/threads/fixture/artifacts'+video_path)
                page.get_by_test_id('acceptance-criteria').locator('summary').first.click()
                expect(page.get_by_test_id('acceptance-criteria')).to_contain_text('Conserva il contenuto del riferimento fornito')
                expect(page.get_by_test_id('acceptance-criteria')).to_contain_text('Da correggere')
                expect(page.get_by_role('link', name='Leggi la richiesta originale completa')).to_have_attribute('href',
                    '/api/threads/fixture/artifacts/mnt/user-data/.righaven-project/requests/original.txt?download=true')
                # Document/project outputs use the same result control, not a video-only flow.
                state['project'] = {**state['project'], 'product_path': '/mnt/user-data/outputs/report/final.docx'}
                page.reload()
                page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$')).click()
                expect(page.get_by_test_id('primary-result').get_by_role('link', name='final.docx',exact=True)).to_be_visible()
                expect(page.get_by_label('Anteprima video')).to_have_count(0)
                # A document without product_path is still discoverable, and old media cannot replace it.
                document = {'path': '/mnt/user-data/outputs/software/release.zip', 'label': 'release.zip',
                            'agent': 'workspace', 'validated': True, 'at': iso(now), 'delivery_id': 'final', 'role': 'export',
                            'open_with': 'Estrarre il pacchetto e seguire README'}
                state['project'] = {**project, 'product_path': '', 'results': [document, project['results'][2]]}
                page.reload()
                page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$')).click()
                expect(page.get_by_test_id('primary-result').get_by_role('link', name='release.zip')).to_be_visible()
                expect(page.get_by_test_id('primary-result')).to_contain_text('Estrarre il pacchetto')
                expect(page.get_by_label('Anteprima video')).to_have_count(0)
                expect(page.get_by_test_id('paired-sources')).to_have_count(0)
                state['project'] = project
                page.reload()
                section('Squadra')
                for name in ('Photocraft', 'Effectcraft', 'Soundcraft', 'Filmcraft'):
                    expect(page.get_by_test_id('team-plan').get_by_text(name, exact=True)).to_be_visible()
                section('Consegne')
                groups = page.get_by_test_id('delivery-group')
                expect(groups).to_have_count(2)
                expect(groups.first).to_contain_text('Consegna incompleta')
                expect(groups.first.get_by_role('link',name='Scarica file e guida')).to_have_attribute('href','/api/threads/fixture/harness-guide?delivery_id=final&format=zip')
                expect(groups.first.get_by_role('heading',name='Risultati da aprire')).to_be_visible()
                expect(groups.first.get_by_role('heading',name='Sorgenti da modificare')).to_be_visible()
                expect(groups.first.get_by_role('link', name='Sorgenti.zip')).to_be_visible()
                expect(groups.first).to_contain_text('montaggio.locale.fcproj')
                expect(groups.first.get_by_role('link', name='bozza.mp4')).to_have_count(0)
                expect(groups.nth(1).get_by_role('link', name='bozza.mp4')).not_to_be_visible()
                page.get_by_test_id('supporting-deliveries').locator('summary').first.click()
                groups.nth(1).locator('summary').first.click()
                expect(groups.nth(1).get_by_role('link', name='bozza.mp4')).to_be_visible()
                page.get_by_test_id('rh-drawer-content').evaluate('(el)=>el.scrollTop=el.scrollHeight')
                section('Stato')
                assert page.get_by_test_id('rh-drawer-content').evaluate('(el)=>el.scrollTop') == 0, 'A new section must start at its own beginning'
                # A correction in progress cannot silently replace the selected version.
                state['project'] = {**project, 'deliveries': [*project['deliveries'],
                    {'id':'next','title':'Correzione mirata','agent':'workspace','at':'','current':False,
                     'purpose':'delivery','category':'version','version':3,'execution_status':'running','technical_status':'not_verified','issues':[]},
                    {'id':'check','title':'Controllo della versione 2','agent':'workspace','at':iso(now),'current':False,
                     'purpose':'review','category':'review','technical_status':'passed','issues':[],
                     'review':{'target_delivery_id':'final','target_version':2,'target_label':'Versione 2','status':'needs_revision',
                        'validated':True,'matches_current_brief':True,'report_path':'/mnt/user-data/outputs/review/report.json','correction_count':2}}]}
                page.reload()
                page.get_by_role('button',name='Apri risultato',exact=True).click()
                expect(page.get_by_test_id('selected-version')).to_contain_text('Versione 2')
                expect(page.get_by_test_id('selected-version')).to_contain_text('Versione 3 in lavorazione')
                expect(page.get_by_test_id('paired-sources').get_by_role('link',name='Sorgenti.zip')).to_be_visible()
                section('Consegne')
                expect(page.get_by_test_id('version-review').first).to_contain_text('Correzioni richieste · versione 2')
                expect(page.get_by_test_id('delivery-group').filter(has_text='Correzione mirata').first).to_contain_text('In lavorazione')
                if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir/'revisioni-mobile.png'))
                # Technical recovery must not masquerade as approval or hide partial work.
                state['project'] = {**project, 'version_selection': {'approved':'final','candidate':'recovered','partial':'interrupted'},
                    'deliveries': [{**d,'version_state':'approved' if d['id']=='final' else 'partial'} for d in project['deliveries']] + [
                        {'id':'recovered','title':'Recupero senza generazione','agent':'workspace','at':iso(now),'current':False,
                         'purpose':'delivery','category':'version','version':4,'execution_status':'completed',
                         'technical_status':'passed','version_state':'candidate','issues':[],
                         'recovery':{'status':'verified','session_error':'provider_quota','message':'Verified saved files'}},
                        {'id':'interrupted','title':'Lavoro interrotto','agent':'workspace','at':iso(now),'current':False,
                         'purpose':'delivery','category':'version','version':5,'execution_status':'paused',
                         'technical_status':'not_verified','version_state':'partial','issues':[]}]}
                page.reload(); section('Consegne')
                expect(page.get_by_test_id('version-selection')).to_contain_text('Ultima approvata: Versione 2')
                expect(page.get_by_test_id('version-selection')).to_contain_text('Ultima candidata: Versione 4')
                recovered = page.get_by_test_id('delivery-group').filter(has_text='Recupero senza generazione').first
                expect(recovered).to_contain_text('Candidata · da valutare')
                expect(recovered).to_contain_text('senza nuova generazione')
                expect(page.get_by_test_id('delivery-group').filter(has_text='Lavoro interrotto').first).to_contain_text('Parziale · non verificata')
                state['project'] = project
                page.reload()
                section('Attività')
                card = page.get_by_test_id('delegate-job')
                expect(card.get_by_text('18 min', exact=False).first).to_be_visible()
                card.get_by_text('Tempi e segnali osservati', exact=True).click()
                expect(card.get_by_text('Non è una stima di consegna.', exact=False)).to_be_visible()
                page.reload()
                expect(page.get_by_test_id('harness-summary')).to_have_text('Render finale · 12/48 campioni')
                expect(page.get_by_test_id('harness-drawer')).to_have_count(0)
                state['job'] = {**job, 'phase': 'failed', 'summary': 'Quota esaurita', 'finished_at': iso(now)}
                state['project'] = {**project, 'status': 'blocked', 'attention': {
                    'code': 'provider_quota', 'message': 'Il servizio AI ha esaurito la quota: i file salvati restano disponibili.',
                    'action': 'Scegli un servizio disponibile oppure attendi il ripristino.'}}
                page.evaluate("window.showThread('fixture',false,false,true)")
                expect(page.get_by_test_id('harness-status')).to_have_text('Il lavoro è in pausa', timeout=7000)
                expect(page.get_by_role('link', name='Apri La tua squadra')).to_be_visible()
                page.evaluate('window.failContinue=true')
                page.get_by_role('button', name='Riprendi lavoro').click()
                expect(page.get_by_role('alert')).to_contain_text('Non riesco a inviare')
                expect(page.get_by_role('button', name='Riprendi lavoro')).to_be_enabled()
                page.evaluate('window.failContinue=false')
                page.get_by_role('button', name='Riprendi lavoro').click()
                assert page.evaluate('window.continued') == 2
                expect(page.get_by_role('button', name='Ripresa richiesta…')).to_be_disabled()
                expect(page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$'))).to_be_enabled()
                state['unavailable'] = True
                expect(page.get_by_text('Aggiornamenti non disponibili:', exact=False)).to_be_visible(timeout=7000)
                expect(page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$'))).to_be_enabled()
                state['unavailable'] = False
                state['project'] = {**project, 'user_control':{'paused':True}}
                state['job'] = {**job,'phase':'failed','resources_reclaimed':True,'finished_at':iso(now)}
                page.reload(); page.evaluate("window.showThread('fixture',false,false,false)")
                expect(page.get_by_test_id('harness-status')).to_have_text('Progetto in pausa')
                page.get_by_role('button',name='Riprendi lavoro',exact=True).click()
                page.wait_for_function('window.continued === 1')
                expect(page.get_by_text('In pausa. I file salvati sono conservati.',exact=True)).to_have_count(0)
                assert state['project']['user_control']['paused'] is False
                state['project'] = {**project, 'status': 'ready', 'product_path': video_path, 'quality_status': 'passed',
                    'deliveries': [{**d, 'technical_status': 'passed', 'issues': []} for d in project['deliveries']]}
                page.evaluate("window.showThread('fixture',false,false,false)")
                expect(page.get_by_test_id('harness-status')).to_have_text('Il risultato è pronto', timeout=7000)
                expect(page.get_by_role('button', name='Riprendi lavoro')).to_have_count(0)
                page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$')).click()
                expect(page.get_by_text('Prodotto finale', exact=True)).to_be_visible()
                page.evaluate("window.showThread('another-conversation',false,false,false)")
                expect(dock).to_have_count(0)
                page.evaluate("window.showThread('fixture',false,false,false)")
                expect(page.get_by_test_id('harness-status')).to_have_text('Il risultato è pronto')
                state['project'] = {**state['project'], 'status': 'review', 'quality_status': 'needs_review'}
                expect(page.get_by_test_id('harness-status')).to_have_text('Una versione è disponibile', timeout=7000)
                expect(page.get_by_role('button', name='Riprendi lavoro')).to_have_count(0)
                page.get_by_role('button', name=re.compile('^(Apri risultato|Apri consegna)$')).click()
                page.get_by_role('button', name='Ho verificato: accetta questa versione').click()
                expect(page.get_by_test_id('harness-status')).to_have_text('Il risultato è pronto')
                expect(page.get_by_text('Questa versione è stata accettata da te.')).to_be_visible()
                # A waiting conversation is not an inactive model; cancelling
                # its ticket must remain distinct from stopping a running worker.
                state['job']={**job,'phase':'queued','started_at':'','deadline_at':'','queue_position':2,
                              'summary':'In attesa della squadra','operations':[],'can_stop':True}
                state['project']={**project,'status':'working'}
                page.reload();page.evaluate("window.showThread('fixture',true,false,true)")
                expect(page.get_by_test_id('harness-status')).to_have_text('In attesa del proprio turno')
                section('Attività')
                expect(page.get_by_test_id('queue-position')).to_contain_text('Posizione in coda: 2')
                state['job'].update(queue_reason='preload',queue_detail='Il precaricamento sta liberando le risorse per questa chat.',queue_activity_since=job['created_at'])
                expect(page.get_by_test_id('harness-status')).to_have_text('Il precaricamento lascia spazio alla chat')
                expect(page.get_by_test_id('queue-position')).to_contain_text('Il precaricamento sta liberando le risorse')
                expect(page.get_by_test_id('queue-position')).to_contain_text('Risorse occupate da')
                expect(page.get_by_text('Avanzamento da verificare',exact=True)).to_have_count(0)
                page.get_by_role('button',name='Annulla attesa',exact=True).click()
                expect(page.get_by_role('button',name='Arresto richiesto…',exact=True)).to_be_disabled()
                # Selecting a two-page proof does not turn it into a full version.
                state['job']={**job,'phase':'completed'}
                state['project']={**project,'status':'review','deliveries':[
                    {**project['deliveries'][0],'purpose':'preview','category':'sample','version':None,
                     'technical_status':'passed','issues':[], 'finalization_pending':['Pacchetto portabile da preparare']}]}
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                section('Risultato')
                expect(page.get_by_test_id('selected-version')).to_contain_text('Campione')
                expect(page.get_by_test_id('selected-version')).not_to_contain_text('Versione 2')
                expect(page.get_by_role('button',name='Ho verificato: accetta questa versione')).to_have_count(0)
                expect(page.get_by_test_id('selected-version').get_by_text('Prima della consegna finale: Pacchetto portabile da preparare',exact=True)).to_be_visible()
                # A new sample remains visible while the next correction runs;
                # a stale selected preview must not pin the old video forever.
                state['project']={**project,'status':'review',
                    'product_path':project['results'][-1]['path'],
                    'latest_sample':project['results'][0],
                    'deliveries':[{**project['deliveries'][0],'current':False,'purpose':'preview','category':'sample'},
                                  {**project['deliveries'][1],'current':True,'category':'sample'}]}
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                section('Risultato')
                expect(page.get_by_test_id('latest-sample')).to_contain_text('Ultimo campione disponibile')
                expect(page.get_by_test_id('primary-result').get_by_role('link')).to_have_attribute('href',re.compile('preview.mp4'))
                expect(page.get_by_test_id('selected-version')).to_contain_text('Robot con musica')
                # A complete delivery keeps precedence over older samples.
                state['project']={**project,'status':'review','latest_sample':project['results'][-1]}
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                section('Risultato')
                expect(page.get_by_test_id('latest-sample')).to_have_count(0)
                expect(page.get_by_test_id('primary-result').get_by_role('link')).to_have_attribute('href',re.compile('preview.mp4'))
                # A follow-up project in the same chat produces a newer sample
                # without replacing the old final. Polling must display it with
                # its own sources, guide and audio, never the old approval.
                new_sample={**project['results'][0], 'path':'/mnt/user-data/outputs/new/sample.epub',
                            'label':'sample.epub','delivery_id':'sample-new','at':iso(now+timedelta(minutes=1))}
                sample_sources={**project['results'][1],'path':'/mnt/user-data/outputs/new/EPUB-sources.zip',
                                'label':'EPUB-sources.zip','delivery_id':'sample-new','at':new_sample['at'],
                                'open_with':'Estrarre e aprire in Calibre','editability':'XHTML e CSS modificabili'}
                sample_delivery={**project['deliveries'][1],'id':'sample-new','title':'Campione del nuovo progetto',
                                 'at':new_sample['at'],'category':'sample','technical_status':'passed'}
                old_audio={**project['results'][0],'path':'/mnt/user-data/outputs/filmcraft/old.wav','label':'old.wav','role':'export'}
                state['project']={**project,'status':'ready','quality_status':'accepted_by_user',
                    'latest_sample':new_sample,
                    'deliveries':[{**project['deliveries'][0],'technical_status':'passed'},sample_delivery],
                    'results':project['results']+[new_sample,sample_sources,old_audio]}
                # No reload: reproduce the transition while the result is open.
                expect(page.get_by_test_id('primary-result').get_by_role('link')).to_have_attribute('href',re.compile('sample.epub'),timeout=15000)
                expect(page.get_by_test_id('latest-sample')).to_be_visible()
                expect(page.get_by_test_id('selected-version')).to_contain_text('Campione del nuovo progetto')
                expect(page.get_by_test_id('selected-version')).not_to_contain_text('Consegna finale')
                expect(page.get_by_test_id('paired-sources')).to_contain_text('EPUB-sources.zip')
                expect(page.get_by_test_id('paired-sources')).not_to_contain_text('montaggio.locale.fcproj')
                expect(page.get_by_role('button',name='Ho verificato: accetta questa versione')).to_have_count(0)
                expect(page.get_by_text('Questa versione è stata accettata da te.',exact=True)).to_have_count(0)
                page.get_by_test_id('previous-delivery').locator('summary').click()
                expect(page.get_by_test_id('previous-delivery')).to_contain_text('Robot con musica')
                expect(page.get_by_test_id('previous-delivery').get_by_role('link',name='preview.mp4',exact=True)).to_have_attribute('href',re.compile('preview.mp4'))
                expect(page.get_by_test_id('previous-delivery')).to_contain_text('Sorgenti.zip')
                page.get_by_test_id('project-guide').locator('summary').first.click()
                expect(page.get_by_test_id('delivery-download').get_by_role('link',name='Scarica guida',exact=True)).to_have_attribute('href',re.compile('delivery_id=sample-new'))
                if args.screenshots_dir: page.screenshot(path=str(args.screenshots_dir / ('new-sample-%d.png'%viewport['width'])))
                # For a video sample the separate soundtrack must also belong
                # to that sample, rather than to the preserved delivery.
                video_sample={**new_sample,'path':'/mnt/user-data/outputs/new/sample.mp4','label':'sample.mp4'}
                sample_audio={**new_sample,'path':'/mnt/user-data/outputs/new/current.wav','label':'current.wav'}
                state['project']={**state['project'],'latest_sample':video_sample,
                    'results':project['results']+[video_sample,sample_sources,old_audio,sample_audio]}
                expect(page.get_by_label('Traccia audio disponibile')).to_have_attribute('src',re.compile('/new/current.wav'),timeout=15000)
                expect(page.locator('audio[src*="old.wav"]')).to_have_count(0)
                # A newer support contribution must not take over the product preview.
                support={**video_sample,'path':'/mnt/user-data/outputs/support/audio.wav','label':'audio.wav',
                         'delivery_id':'support-new','at':iso(now+timedelta(minutes=3)),'role':'export'}
                state['project']['deliveries'].append({**sample_delivery,'id':'support-new','purpose':'work','category':'contribution','at':support['at']})
                state['project']['results'].append(support)
                page.wait_for_timeout(2500)
                expect(page.get_by_test_id('primary-result').get_by_role('link')).to_have_attribute('href',re.compile('sample.mp4'))
                # Real regression: a render requested after a CAD delivery is
                # purpose=delivery with a preview-role PNG, not a sample job.
                # Show it even when blocked, without approving it or mixing sources.
                baseline={**project['results'][0],'path':'/mnt/user-data/outputs/cad/model.stl','label':'model.stl'}
                cad_source={**project['results'][1],'path':'/mnt/user-data/outputs/cad/model.FCStd','label':'model.FCStd','role':'editable_source'}
                render={**new_sample,'path':'/mnt/user-data/outputs/render/model.png','label':'model.png','role':'preview','delivery_id':'render-new'}
                render_source={**sample_sources,'path':'/mnt/user-data/outputs/render/render.py','label':'render.py','role':'editable_source','delivery_id':'render-new'}
                render_delivery={**sample_delivery,'id':'render-new','title':'Render del modello esistente','purpose':'delivery','category':'version',
                                 'version':3,'current':False,'technical_status':'needs_revision','issues':['Verifica della consegna da completare']}
                state['project']={**project,'status':'ready','quality_status':'accepted_by_user','product_path':baseline['path'],'latest_sample':None,
                                  'deliveries':[{**project['deliveries'][0],'technical_status':'passed'},render_delivery],
                                  'results':[baseline,cad_source,render,render_source]}
                expect(page.get_by_test_id('primary-result').get_by_role('img')).to_have_attribute('src',re.compile('/render/model.png'),timeout=15000)
                expect(page.get_by_test_id('latest-result')).to_contain_text('Ultimo risultato disponibile')
                expect(page.get_by_test_id('selected-version')).to_contain_text('Render del modello esistente')
                expect(page.get_by_test_id('selected-version')).to_contain_text('Verifica della consegna da completare')
                expect(page.get_by_test_id('selected-version')).not_to_contain_text('Consegna finale')
                expect(page.get_by_test_id('paired-sources')).to_contain_text('render.py')
                expect(page.get_by_test_id('paired-sources')).not_to_contain_text('model.FCStd')
                expect(page.get_by_text('Questa versione è stata accettata da te.',exact=True)).to_have_count(0)
                expect(page.get_by_role('button',name='Ho verificato: accetta questa versione')).to_have_count(0)
                page.get_by_test_id('previous-delivery').locator('summary').click()
                expect(page.get_by_test_id('previous-delivery')).to_contain_text('model.stl')
                state['project']['results']=[baseline,cad_source,{**render,'validated':False},render_source]
                expect(page.get_by_test_id('primary-result').get_by_role('link')).to_have_attribute('href',re.compile('model.stl'),timeout=15000)
                expect(page.get_by_test_id('latest-result')).to_have_count(0)
                # When a later final arrives, an earlier sample stops overriding
                # it, even if latest_sample remains in the API response.
                state['project']={**project,'status':'review','latest_sample':new_sample,
                    'deliveries':[{**project['deliveries'][0],'at':iso(now+timedelta(minutes=2))},sample_delivery]}
                expect(page.get_by_test_id('primary-result').get_by_role('link')).to_have_attribute('href',re.compile('preview.mp4'),timeout=15000)
                expect(page.get_by_test_id('latest-sample')).to_have_count(0)
                expect(page.get_by_test_id('previous-delivery')).to_have_count(0)
                state['project']={**project,'status':'review','deliveries':[
                    {**project['deliveries'][0],'unchanged_content':True,'change_kind':'metadata','content_version':1}]}
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                section('Risultato')
                expect(page.get_by_test_id('selected-version')).to_contain_text('Metadati aggiornati · versione 1 invariata')
                # A candidate PDF remains directly downloadable even when the turn stops before approval.
                pdf_path='/mnt/user-data/outputs/candidate/Carousel.pdf'
                pdf_result={**project['results'][0],'path':pdf_path,'label':'Carousel.pdf','role':'export','delivery_id':'final','validated':True}
                state['project']={**project,'status':'review','product_path':pdf_path,'results':[pdf_result],
                    'attention':{'code':'incomplete_objective','message':'Verifiche incomplete','action':'Valuta il risultato.'}}
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                expect(page.get_by_role('link',name='Scarica Carousel.pdf',exact=True)).to_be_visible()
                page.get_by_role('button',name='Apri risultato',exact=True).click()
                expect(page.get_by_title('Anteprima PDF')).to_have_attribute('src',re.compile('Carousel.pdf$'))
                expect(page.get_by_test_id('primary-result').get_by_role('link',name='Carousel.pdf',exact=True)).to_be_visible()
                # Old observations are curated only on explicit request, scoped
                # to this chat; proposing never implies accepting the lessons.
                state['pending_observations']=3
                page.reload();page.evaluate("window.showThread('fixture',true,false,false)")
                section('Lezioni')
                expect(page.get_by_role('button',name='Valuta le osservazioni',exact=True)).to_be_disabled()
                page.evaluate("window.showThread('fixture',false,false,false)")
                expect(page.get_by_role('button',name='Valuta le osservazioni',exact=True)).to_be_enabled()
                continued_before=page.evaluate('window.continued')
                page.get_by_role('button',name='Valuta le osservazioni',exact=True).click()
                expect(page.get_by_test_id('experience-panel')).to_contain_text('Una lezione salvata senza modificare il progetto.')
                assert state.get('curation_requested')==1
                assert page.evaluate('window.continued')==continued_before
                assert state.get('lesson_accepted',False) is False
                state['pending_observations']=99;state['current_pending']=0
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                section('Lezioni')
                expect(page.get_by_role('button',name='Valuta le osservazioni',exact=True)).to_be_disabled()
                expect(page.get_by_test_id('curation-controls')).to_contain_text('0 osservazioni significative')
                state.pop('current_pending')
                state['foreign_lessons_only']=True
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)");section('Lezioni')
                expect(page.get_by_test_id('general-lesson')).to_have_count(0)
                page.get_by_role('button',name='Archivio personale',exact=True).click()
                expect(page.get_by_test_id('general-lesson')).to_have_count(1)
                state.pop('foreign_lessons_only')
                # The component source map and measured offset belong beside the
                # selected delivery, rather than in a wall of execution messages.
                state['project']={**project,'deliveries':[{**project['deliveries'][0],
                    'source_coverage':{'status':'incomplete','components':[{'name':'Musica','tool':'soundcraft','status':'incomplete','sources':[]}]},
                    'timing':{'status':'failed','cues':[{'name':'Impatto','status':'failed','delta_seconds':1.5}]}}]}
                page.reload();page.evaluate("window.showThread('fixture',false,false,false)")
                section('Risultato')
                page.get_by_test_id('component-sources').locator('summary').click()
                expect(page.get_by_test_id('component-sources')).to_contain_text('soundcraft')
                expect(page.get_by_test_id('component-sources')).to_contain_text('sorgenti incompleti')
                page.get_by_test_id('delivery-timing').locator('summary').click()
                expect(page.get_by_test_id('delivery-timing')).to_contain_text('1.5 s di scarto')
                state['project']={**project,'status':'working','user_control':{}}
                state['job']={**job,'phase':'creating','resources_reclaimed':False}
                state['extra_jobs']=[{**job,'job_id':'rh-job-abcdef123456','phase':'creating','role_title':'Revisore indipendente'}]
                page.reload()
                expect(dock).to_contain_text('2 incarichi attivi',timeout=10000)
                page.get_by_role('button',name='Consegna ora',exact=True).click()
                expect(dock).to_contain_text('Consegna richiesta',timeout=10000)
                self_check=state['project']['user_control']
                assert self_check['deliver_now'] is True
                expect(page.get_by_role('button',name='Consegna richiesta…',exact=True)).to_be_disabled()
                # A guided project lives inside the same card: path strip, inline owner decision and the Path tab.
                text=lambda it,en:{'it':it,'en':en}
                state['journey']={'recipe_id':'data-pipeline','recipe':{'title':'Pipeline dati end-to-end','skills':['skill-data-pipeline'],'environment':'pipeline-dati'},
                    'revision':4,'answers':{'goal':'Dashboard semplice con dati di esempio'},'complete':False,'current':'understand','awaiting_owner':['understand'],
                    'stages':[{'id':'understand','title':text('Comprensione e catalogo','Understanding'),'outcome':text('Schema documentato','Documented schema'),'status':'review','available':True,'gate':True,
                               'note':'Catalogo pronto','evidence':[{'path':'/mnt/user-data/outputs/catalogo.md','sha256':'a'*64}]},
                              {'id':'design','title':text('Progettazione','Design'),'outcome':text('Indicatori concordati','Agreed measures'),'status':'pending','available':False,'gate':True,'note':'','evidence':[]},
                              {'id':'lab','title':text('Laboratorio','Laboratory'),'outcome':text('Replica vuota','Empty replica'),'status':'pending','available':False,'gate':False,'note':'','evidence':[]}]}
                page.reload()
                strip=dock.get_by_test_id('project-journey')
                expect(strip).to_contain_text('Pipeline dati end-to-end')
                expect(strip.get_by_test_id('journey-goal')).to_have_text('Obiettivo: Dashboard semplice con dati di esempio')
                expect(strip.get_by_test_id('journey-progress')).to_have_text('0/3 fasi concluse')
                decision=strip.get_by_test_id('journey-decision')
                expect(decision.get_by_role('link',name='catalogo.md')).to_be_visible()
                decision.get_by_role('button',name='Approva fase',exact=True).click()
                expect(strip.get_by_test_id('journey-progress')).to_have_text('1/3 fasi concluse')
                assert state['journey_decision']=={'stage_id':'understand','action':'approve','expected_revision':4,'note':''},state['journey_decision']
                strip.get_by_role('button',name='Tutte le fasi',exact=True).click()
                phases=page.get_by_test_id('journey-phases')
                expect(phases.get_by_test_id('journey-phase')).to_have_count(3)
                expect(phases.get_by_test_id('journey-phase').nth(2)).to_contain_text('senza approvazione')
                nav=page.get_by_test_id('harness-drawer').get_by_role('navigation')
                expect(nav.get_by_role('button',name='Percorso',exact=True)).to_have_attribute('aria-current','page')
                expect(nav.get_by_role('button',name='Tavole',exact=True)).to_have_count(0)
                expect(nav.get_by_role('button',name='Attività',exact=True)).to_have_count(0)
                section('Stato')
                expect(page.get_by_test_id('project-position')).to_contain_text('Fase del percorso: Progettazione')
                page.get_by_role('button', name='Chiudi dettagli del progetto').click()
                state.pop('journey')
                assert not errors, errors
                browser.close()
            print('Browser OK: guided path inside the project card; real Tailwind dock visible beside composer on desktop/mobile during chat scrolling; playable preview; adaptive team; 18-minute clock; quota pause; continue action; network recovery; reload and conversation isolation.')
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
