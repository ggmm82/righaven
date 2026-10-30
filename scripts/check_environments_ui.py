#!/usr/bin/env python3
"""Actual React page flows with declared API fixtures; server CRUD is ci_http."""
import argparse,json,subprocess,tempfile,threading,time,copy,re
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);parser.add_argument('--screenshots-dir',type=Path);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=args.node_modules.resolve()
    state={'environments':[],'skills':[{'name':'skill-'+n,'kind':'tool','description':n+' capability','enabled':n!='blender','tools':[n],'error':''} for n in ('d2','pandoc','blender')], 'presets':[{'id':'progettazione','name':'Progettazione','purpose':'Transform ideas into editable models','skills':['skill-d2','skill-pandoc'],'missing_tools':[]}], 'dynamic':True,'can_import_software':True,'can_configure_resources':True,'reuse_policy':{'criteria':'programmi coperti, poi meno programmi mancanti','eligible':'preload'}}
    resources={'settings':{'mode':'auto','cpus':1.5,'memory_mib':1536,'model_wait_seconds':120,'max_workers':2},'effective':{'cpus':1.5,'memory_mib':3970},'warning':''}
    state['parallelism']={'limit':2,'preparations':0,'terminals':0,'terminal_limit':2,'monitor':{'observed_at':time.time(),'configured_limit':2,'cpus':1.5,'memory_mib':3970,'allocated_cpus':.5,'allocated_memory_mib':1024,'active':{'worker':1,'build':0,'terminal':0,'control':0},'waiting':{'worker':0,'build':1,'terminal':0,'control':0},'blocked':False}}
    posts=[];fail=[False];transfer={};terminal={};log_reply={"text":"Trusted installer log"};log_fail=[False]
    library={'tools':[{'id':'d2','name':'D2','version':'0.9.0'},{'id':'provider-agy','name':'Antigravity CLI','version':'1.4.7'}],'versions':[],'jobs':[],'defaults':{}}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);(root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);');(root/'config.ts').write_text('export const getBackendBaseURL=()=>location.origin;');(root/'link.tsx').write_text('import React from "react";export default function Link(p:any){return <a {...p}/>;}')
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:"it-IT"}};')
        entry=root/'entry.tsx';entry.write_text('import React from "react";import{createRoot}from"react-dom/client";import Page from '+json.dumps(str(repo/'frontend/environments-page.tsx'))+';createRoot(document.getElementById("root")!).render(<Page/>);')
        build='require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps({'entryPoints':[str(entry)],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':{'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts'),'next/link':str(root/'link.tsx')}})+');'
        subprocess.run(['node','-e',build],check=True)
        (root/'source.css').write_text('@import "tailwindcss";\n@source '+json.dumps(str(repo/'frontend/environments-page.tsx'))+';\n@source '+json.dumps(str(repo/'frontend/tool-versions.tsx'))+';\n')
        subprocess.run(['node',str(modules/'@tailwindcss/cli/dist/index.mjs'),'-i',str(root/'source.css'),'-o',str(root/'app.css')],env={**__import__('os').environ,'NODE_PATH':str(modules)},check=True,capture_output=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,value,kind='application/json',code=200):
                self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(value if isinstance(value,bytes) else value.encode())
            def do_GET(self):
                if self.path.endswith('/resources/settings'):return self.send(json.dumps(resources))
                if self.path.endswith('/releases'):return self.send(json.dumps({'releases':[{'version':'1.4.7'}]}))
                if self.path.endswith('/history'):
                    profile=state['environments'][0]
                    return self.send(json.dumps({'items':[{'id':'a'*64,'saved_at':100,'definition':profile},{'id':'b'*64,'saved_at':90,'definition':{**profile,'purpose':'Earlier configuration'}}]}))
                if '/tool-versions' in self.path:return self.send(json.dumps(library))
                if '/transfers/' in self.path:return self.send(json.dumps(transfer))
                if '/terminals/' in self.path:return self.send(json.dumps(terminal))
                if self.path.endswith('/log'):
                    return self.send(json.dumps({'detail':'Temporary failure'} if log_fail[0] else log_reply),code=503 if log_fail[0] else 200)
                if self.path.startswith('/api/'):return self.send(json.dumps(state))
                if self.path in ('/app.js','/app.css'):return self.send((root/self.path[1:]).read_bytes(),'text/javascript' if self.path.endswith('.js') else 'text/css')
                self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><div id="root"></div><script src="/app.js"></script>','text/html')
            def do_POST(self):
                raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
                value={} if self.path.endswith('/software-import') else json.loads(raw or '{}');posts.append((self.path,value))
                if self.path.endswith('/share'):
                    if value.get('confirm'):
                        assert value['preview_hash']=='preview-hash'
                        return self.send(json.dumps({'published':True}))
                    return self.send(json.dumps({'manifest':{'id':value['id'],'version':value['version'],'tools':['d2']},'preview_hash':'preview-hash'}))
                if '/restore/' in self.path:return self.send(json.dumps(state['environments'][0]))
                if self.path.endswith('/resources/rebalance'):
                    state['parallelism']['monitor'].update(allocated_cpus=1.5,allocated_memory_mib=2048);return self.send(json.dumps({'updated':1,'unchanged':0,'pending':0,'message':'Budget attivo riassegnato'}))
                if self.path.endswith('/resources/settings'):
                    resources['settings']=value;state['parallelism']['limit']=value['max_workers'];return self.send(json.dumps(resources))
                if self.path.endswith('/prepare-preloaded'):
                    return self.send(json.dumps({'environments':[p['name'] for p in state['environments'] if p['deployment']['mode']=='preload']}))
                if self.path.endswith('/tool-versions/default'):
                    library['defaults'][value['tool']]=value['revision'];return self.send(json.dumps({'preparing_environments':0 if value['tool'].startswith('provider-') else 1}))
                if self.path.endswith('/tool-versions'):
                    library['versions']=[{'id':'a'*64,'tool':value['tool'],'version':'1.4.7','state':'ready'}]
                    library['jobs']=[{'id':'b'*32,'tool':value['tool'],'version':value['version'],'resolved_version':'1.4.7','state':'ready'}]
                    return self.send('{"accepted":true}')
                if self.path.endswith('/software-export') or self.path.endswith('/software-import'):
                    transfer.update(id='b'*32,name='progettazione',kind='import' if self.path.endswith('/software-import') else 'export',state='ready',size_bytes=104857600,image_bytes=104800000,layer_count=3,message='Ambiente importato e verificato' if self.path.endswith('/software-import') else 'Pacchetto pronto al download')
                    return self.send(json.dumps(transfer),code=202)
                if self.path.endswith('/terminal'):
                    terminal.update(id='c'*32,profile='progettazione',text='righaven$ ',finished=False,limits={'cpus':1.5,'memory_mib':1536})
                    return self.send(json.dumps(terminal),code=201)
                if '/terminals/' in self.path and self.path.endswith('/input'):
                    terminal['text']+='\nExecuted: '+value['text'];return self.send('{"accepted":true}')
                if fail[0]:return self.send('{"detail":"Name already exists"}',code=409)
                profile={**value,'tools':['d2','pandoc'],'deployment':{'mode':value.get('mode','on_demand'),'ephemeral':False,'preload_tools':value.get('preload_tools'),'tool_versions':value.get('tool_versions',{})},'runtime':{'status':'on_demand'}}
                state['environments']=[profile];self.send(json.dumps(profile))
            do_PUT=do_POST
            def do_DELETE(self):
                terminal['finished']=True;return self.send('{"accepted":true}')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1100,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.get_by_role('button',name='Aggiungi ambiente',exact=True).click()
                expect(page.get_by_role('dialog',name='Aggiungi ambiente')).to_be_visible()
                expect(page.get_by_role('link',name='Esplora ambienti nella Gallery')).to_have_attribute('href','/workspace/gallery?category=environment')
                page.get_by_role('button',name='Scegli un modello',exact=True).click()
                expect(page.get_by_role('dialog',name='Modelli iniziali')).to_be_visible()
                page.get_by_role('button',name='Personalizza Progettazione').click()
                dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
                expect(dialog.get_by_label('Nome ambiente',exact=True)).to_have_value('Progettazione')
                expect(dialog.get_by_role('group',name='Skill disponibili nel profilo')).to_contain_text('Uso di strumenti')
                blender=dialog.get_by_role('checkbox',name=re.compile('^blender '));expect(blender).to_be_disabled()
                dialog.get_by_role('radio',name=re.compile('^Precarica')).check()
                programs=dialog.get_by_role('group',name='Programmi da tenere pronti');programs.get_by_label('pandoc',exact=True).uncheck()
                dialog.get_by_text('Versioni e opzioni avanzate',exact=True).click();dialog.get_by_label('Versione d2',exact=True).select_option('latest')
                dialog.get_by_role('button',name='Salva ambiente').click();expect(page.get_by_role('dialog')).to_have_count(0)
                card=page.get_by_test_id('environment-card');expect(card).to_contain_text('Progettazione')
                expect(page.get_by_test_id('profile-reuse-policy')).to_contain_text('Criterio di scelta: programmi coperti, poi meno programmi mancanti')
                expect(card.get_by_test_id('profile-reuse')).to_contain_text('Nessun incarico l’ha ancora usato come base.')
                assert posts[-1][1]['preload_tools']==['d2'];assert posts[-1][1]['tool_versions']=={'d2':'latest'}
                page.reload();card.locator('summary').filter(has_text='Opzioni').click();card.get_by_role('button',name='Configura',exact=True).click();expect(programs.get_by_label('pandoc',exact=True)).not_to_be_checked()
                dialog.get_by_text('Versioni e opzioni avanzate',exact=True).click();expect(dialog.get_by_label('Versione d2',exact=True)).to_have_value('latest')
                dialog.get_by_label('Scopo ambiente').fill('Uncommitted purpose survives polling');page.wait_for_timeout(5500)
                expect(dialog.get_by_label('Scopo ambiente')).to_have_value('Uncommitted purpose survives polling')
                fail[0]=True;dialog.get_by_role('button',name='Salva ambiente').click();expect(dialog.get_by_role('alert')).to_contain_text('Name already exists')
                box=dialog.get_by_role('alert').bounding_box();assert box and 0<=box['y']<900,'Validation error is offscreen'
                expect(dialog.get_by_label('Scopo ambiente')).to_have_value('Uncommitted purpose survives polling')
                dialog.get_by_role('button',name='Annulla',exact=True).click();expect(card.get_by_role('button',name='Configura',exact=True)).to_be_focused()
                fail[0]=False

                if not card.get_by_role('button',name=re.compile('^Gestisci ')).is_visible():card.locator('summary').filter(has_text='Opzioni').click()
                card.get_by_role('button',name=re.compile('^Gestisci ')).click();dialog.get_by_role('button',name='Clona',exact=True).click()
                expect(dialog.get_by_label('Nome ambiente')).to_have_value('Progettazione — copia')
                dialog.get_by_text('Versioni e opzioni avanzate',exact=True).click();expect(dialog.get_by_label('Versione d2',exact=True)).to_have_value('latest')
                page.keyboard.press('Escape');expect(card.get_by_role('button',name=re.compile('^Gestisci '))).to_be_focused()
                # A saved selection is not an active capability after a global disable.
                state['skills'].append({'name':'method-render','kind':'method','description':'Rendering method','enabled':True,'tools':['blender'],'error':''})
                state['environments'][0]['skills']+=['skill-blender','method-render']
                page.reload();card.locator('summary').filter(has_text='Opzioni').click();card.get_by_role('button',name='Configura',exact=True).click()
                disabled_cli=dialog.get_by_role('checkbox',name=re.compile('^blender '))
                expect(disabled_cli).not_to_be_checked();expect(disabled_cli).to_be_disabled()
                disabled_method=dialog.get_by_role('checkbox',name=re.compile('^method-render '))
                expect(disabled_method).not_to_be_checked();expect(disabled_method).to_be_disabled()
                expect(dialog.get_by_text('Strumenti selezionati: d2, pandoc',exact=True)).to_be_visible()
                page.keyboard.press('Escape')
                state['environments'][0]['runtime']={'status':'on_demand'}
                state['environments'][0]['configuration_change']={'code':'selection_changed','message':'Le versioni selezionate sono cambiate. La variante precedente è ancora conservata.','previous_available':True,'previous_providers':[],'requested_providers':[]}
                expect(page.get_by_role('button',name='Da aggiornare (1)',exact=True)).to_be_visible(timeout=8000)
                expect(card.get_by_role('button',name='Aggiorna ambiente',exact=True)).to_be_visible()
                expect(card).to_contain_text('La variante precedente è ancora conservata.')
                state['environments'][0].pop('configuration_change')
                state['environments'][0]['runtime']={'status':'installing','reused_tools':['d2'],'install_tools':['pandoc']}
                expect(card.get_by_test_id('software-reuse')).to_contain_text('1 riutilizzati · 1 da aggiungere o aggiornare',timeout=8000)
                # Version resolution must be visible as active work, not a second prepare button.
                state['environments'][0]['runtime']={'status':'checking_versions'}
                state['environments'][0]['preparation']={'phase':'checking_versions','label':'Verifica delle versioni','active':True,'started_at':time.time()-90,'tool':'wordcraft','version':'v0.11.0','index':2,'total':3}
                expect(card).to_contain_text('wordcraft v0.11.0 · strumento 2 di 3',timeout=10000)
                expect(card.get_by_role('button',name='Segui preparazione')).to_be_visible();expect(card.get_by_role('button',name='Prepara ora')).to_have_count(0)
                job={'profile':'progettazione','thread_id':'own-chat','role':'Revisore','summary':'Controllo la leggibilità','phase':'waiting_model','observed_running':True,'tools':['d2']}
                state['environments'][0].update(runtime={'status':'ready','id':'a'*64},activity={'state':'busy','jobs':[job]})
                state['activity']={'observed':True,'jobs':[job]}
                state['environments'][0].pop('preparation')
                expect(card).to_contain_text('Uso: Occupato',timeout=10000);expect(card).to_contain_text('Controllo la leggibilità')
                page.get_by_role('button',name='Occupati (1)',exact=True).click();expect(card).to_have_count(1)
                state['environments'][0]['activity']={'state':'idle','jobs':[]}
                expect(page.get_by_role('button',name='Occupati (0)',exact=True)).to_be_visible(timeout=8000);expect(card).to_have_count(0)
                state['environments'][0]['activity']={'state':'busy','jobs':[job]}
                expect(page.get_by_role('button',name='Occupati (1)',exact=True)).to_be_visible(timeout=8000);expect(card).to_have_count(1)
                temporary={**job,'profile':'','job_id':'temporary','environment_id':'temporary-runtime','tools':['typst','poppler'],'role':'Impaginazione'}
                state['activity']={'observed':True,'jobs':[job,temporary]}
                temp=page.get_by_role('region',name='Ambienti temporanei in uso')
                expect(temp).to_contain_text('typst, poppler',timeout=8000)
                expect(temp.get_by_role('link',name='Apri la chat dell’incarico')).to_have_attribute('href','/workspace/chats/own-chat')
                state['activity']={'observed':True,'jobs':[job]}
                expect(temp).to_have_count(0,timeout=8000)
                page.get_by_role('button',name='Tutti (1)',exact=True).click()
                page.get_by_text('Attività, trasferimenti e gestione avanzata',exact=False).first.click()
                expect(page.get_by_role('region',name='Monitor delle risorse')).to_contain_text('1024/3970 MiB')
                expect(page.get_by_role('region',name='Monitor delle risorse')).to_contain_text('1 preparazioni')
                page.get_by_role('button',name='Risorse e parallelismo',exact=True).click()
                expect(dialog.get_by_label('Operazioni contemporanee')).to_have_value('2')
                dialog.get_by_label('Operazioni contemporanee').select_option('3')
                page.wait_for_timeout(5200);expect(dialog.get_by_label('Operazioni contemporanee')).to_have_value('3')
                dialog.get_by_role('button',name='Salva limite',exact=True).click();expect(dialog).to_have_count(0)
                assert resources['settings']['max_workers']==3 and resources['settings']['model_wait_seconds']==120
                page.get_by_role('button',name='Risorse e parallelismo',exact=True).click();expect(dialog.get_by_label('Operazioni contemporanee')).to_have_value('3')
                dialog.get_by_role('button',name='Applica budget ai lavori attivi',exact=True).click();expect(dialog).to_have_count(0)
                expect(page.get_by_role('region',name='Monitor delle risorse')).to_contain_text('1.5/1.5 CPU')
                page.get_by_role('button',name='Lavori in corso (1)',exact=True).click();expect(dialog).to_contain_text('Controllo la leggibilità');page.keyboard.press('Escape')
                expect(card.get_by_role('link',name='Apri chat',exact=True).first).to_have_attribute('href','/workspace/chats/own-chat')

                if not card.get_by_role('button',name=re.compile('^Gestisci ')).is_visible():card.locator('summary').filter(has_text='Opzioni').click()
                card.get_by_role('button',name=re.compile('^Gestisci ')).click();dialog.get_by_role('button',name='Dettagli preparazione',exact=True).click()
                expect(dialog.get_by_role('region',name='Dettagli preparazione')).to_contain_text('Trusted installer log')
                # The open detail follows the shared queue and actual new output without a click.
                log_reply['observation']={'phase':'queued','tools':['vectorcraft'],'observed_at':time.time(),'last_output_at':None,'log_bytes':0,'recent_output':'','prerequisite':False,'waiting_on':{'tools':['ffmpeg'],'phase':'installing'}}
                expect(dialog.get_by_role('region',name='Avanzamento osservato')).to_contain_text('Le risorse sono impegnate nelle preparazioni di ffmpeg',timeout=8000)
                log_reply.update(text='CC vector/first.o',observation={'phase':'installing','tools':['vectorcraft'],'observed_at':time.time(),'last_output_at':time.time(),'log_bytes':1600,'recent_output':'CC vector/first.o','prerequisite':False})
                expect(dialog.get_by_role('region',name='Avanzamento osservato')).to_contain_text('CC vector/first.o',timeout=8000)
                log_reply.update(text='CC vector/second.o',observation={**log_reply['observation'],'observed_at':time.time(),'log_bytes':2300,'recent_output':'CC vector/second.o'})
                expect(dialog.get_by_role('region',name='Avanzamento osservato')).to_contain_text('CC vector/second.o',timeout=8000)
                log_fail[0]=True;expect(dialog.get_by_role('alert')).to_contain_text('stato mostrato potrebbe non essere attuale',timeout=8000)
                expect(dialog.get_by_role('region',name='Avanzamento osservato')).to_contain_text('CC vector/second.o')
                log_fail[0]=False;expect(dialog.get_by_role('alert')).to_have_count(0,timeout=8000)
                page.keyboard.press('Escape');
                if not card.get_by_role('button',name=re.compile('^Gestisci ')).is_visible():card.locator('summary').filter(has_text='Opzioni').click()
                card.get_by_role('button',name=re.compile('^Gestisci ')).click()
                dialog.get_by_role('button',name='Esporta programmi e Dockerfile',exact=True).click()
                expect(dialog).to_contain_text('100.0 MiB · immagine Docker verificata (3 livelli)')
                expect(dialog.get_by_role('link',name='Scarica ambiente, Dockerfile e ricetta')).to_have_attribute('href',re.compile('/transfers/[b]+/download$'))
                dialog.get_by_role('button',name='Chiudi trasferimento').click()
                # The server catalogue must supersede a stale selected record,
                # even when the dedicated transfer-status request is unavailable.
                transfer.update(state='working',message='Esportazione immagine',updated_at=10,observed_at=10)
                state['transfers']=[dict(transfer)]
                page.reload();page.get_by_text('Attività, trasferimenti e gestione avanzata',exact=False).first.click();page.get_by_role('button',name='Trasferimenti (1)',exact=True).click()
                expect(dialog).to_contain_text('Esportazione immagine')
                fresh={**transfer,'state':'ready','message':'Pacchetto verificato dal catalogo','updated_at':20,'observed_at':20}
                state['transfers']=[fresh]
                expect(dialog).to_contain_text('Pacchetto verificato dal catalogo',timeout=8000)
                expect(dialog.get_by_role('link',name='Scarica ambiente, Dockerfile e ricetta')).to_be_visible()
                state['transfers']=[{**fresh,'state':'failed','message':'Errore di trasferimento','error_detail':'Docker: no space left on device','updated_at':30,'observed_at':30}]
                expect(dialog).to_contain_text('Errore di trasferimento',timeout=8000)
                dialog.get_by_text('Dettaglio tecnico',exact=True).click();expect(dialog).to_contain_text('no space left on device')
                dialog.get_by_role('button',name='Riprova esportazione',exact=True).click()
                transfer.update(updated_at=40,observed_at=40)
                state['transfers']=[dict(transfer)]
                expect(dialog).to_contain_text('Pacchetto pronto al download',timeout=8000)
                dialog.get_by_role('button',name='Chiudi trasferimento').click()

                if not card.get_by_role('button',name=re.compile('^Gestisci ')).is_visible():card.locator('summary').filter(has_text='Opzioni').click()
                card.get_by_role('button',name=re.compile('^Gestisci ')).click()
                dialog.get_by_label('Importa programmi per Progettazione').set_input_files({'name':'environment.righaven-env.tar','mimeType':'application/x-tar','buffer':b'fixture; actual binary validation runs in Docker'})
                expect(dialog).to_contain_text('Ambiente importato e verificato');dialog.get_by_role('button',name='Chiudi trasferimento').click()

                if not card.get_by_role('button',name=re.compile('^Gestisci ')).is_visible():card.locator('summary').filter(has_text='Opzioni').click()
                card.get_by_role('button',name=re.compile('^Gestisci ')).click()
                with page.expect_popup() as opened:dialog.get_by_role('button',name='Apri terminale',exact=True).click()
                popup=opened.value;expect(popup).to_have_url(re.compile(r'/terminal\?environment=progettazione$'));popup.close();page.keyboard.press('Escape')
                page.get_by_role('button',name='Versioni dei programmi',exact=True).click()
                panel=page.get_by_test_id('tool-versions');panel.locator('select').first.select_option('provider-agy')
                panel.get_by_role('button',name='Cerca release ufficiali').click();panel.get_by_role('button',name='Verifica versione',exact=True).click()
                expect(panel.get_by_label('Versione Antigravity CLI',exact=True).locator('option[value="'+('a'*64)+'"]')).to_have_count(1)
                panel.get_by_label('Versione Antigravity CLI',exact=True).select_option('latest');expect(panel).to_contain_text('Gli ambienti preparati restano disponibili.')
                page.keyboard.press('Escape');page.get_by_role('button',name='Prepara i precaricati').click();expect(page.get_by_role('status')).to_contain_text('precaricato in preparazione');assert posts[-1][0].endswith('/prepare-preloaded')
                # Scrolling down a long list must never put the newly opened content offscreen.
                original=copy.deepcopy(state['environments'][0]);state['environments']=[{**copy.deepcopy(original),'name':'profile-'+str(i),'display_name':'Ambiente '+str(i),'activity':{'state':'idle','jobs':[]}} for i in range(14)]
                state['environments'][-1].update(runtime={'status':'failed','error':'Calibre PDF renderer crashed','failure':{'message':'Calibre: il motore di esportazione PDF è andato in crash.','action':'Riprova la preparazione.','passed_tools':['one','two','three','four','five','six']}})
                page.set_viewport_size({'width':390,'height':844});page.reload()
                last=page.get_by_test_id('environment-card').last;last.scroll_into_view_if_needed();last.locator('summary').filter(has_text='Opzioni').click();last.get_by_role('button',name='Configura',exact=True).click()
                expect(dialog).to_be_visible();expect(dialog.get_by_label('Nome ambiente')).to_have_value('Ambiente 13')
                rect=dialog.bounding_box();assert rect and rect['y']>=0 and rect['y']+rect['height']<=845,rect
                page.keyboard.press('Escape');expect(last.get_by_role('button',name='Configura',exact=True)).to_be_focused()
                expect(last).to_contain_text('Calibre: il motore di esportazione PDF');expect(last).to_contain_text('6 strumenti hanno superato il collaudo')
                expect(last.get_by_role('button',name='Risolvi problema')).to_have_count(1)
                last.get_by_role('button',name='Risolvi problema').click();expect(dialog).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile overflow'
                if args.screenshots_dir:
                    args.screenshots_dir.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(args.screenshots_dir/'environment-details-mobile.png'),full_page=False)
                page.keyboard.press('Escape');page.get_by_role('button',name='Da correggere (1)',exact=True).click();expect(page.get_by_test_id('environment-card')).to_have_count(1)
                page.get_by_role('button',name='Tutti (14)',exact=True).click()
                page.get_by_role('searchbox',name='Cerca ambienti').fill('Ambiente 13')
                expect(page.get_by_test_id('environment-card')).to_have_count(1)
                if not page.get_by_test_id('environment-card').get_by_role('button',name=re.compile('^Gestisci ')).is_visible():page.get_by_test_id('environment-card').locator('summary').filter(has_text='Opzioni').click()
                page.get_by_test_id('environment-card').get_by_role('button',name=re.compile('^Gestisci ')).click()
                dialog.get_by_text(re.compile('^Storico delle configurazioni')).click()
                dialog.get_by_role('button',name='Esamina ripristino').click()
                expect(dialog).to_contain_text('Earlier configuration')
                dialog.get_by_role('button',name='Conferma ripristino').click()
                expect(dialog).to_contain_text('Configurazione ripristinata.')
                dialog.get_by_text('Condividi nel catalogo',exact=True).click()
                dialog.get_by_role('button',name='Anteprima della pubblicazione').click()
                expect(dialog.get_by_role('button',name='Pubblica questa versione')).to_be_disabled()
                dialog.get_by_role('checkbox',name=re.compile('^Ho verificato')).check()
                dialog.get_by_role('button',name='Pubblica questa versione').click()
                expect(dialog).to_contain_text('Versione pubblicata nel catalogo')
                assert any(path.endswith('/share') and value.get('confirm') for path,value in posts)
                assert not errors,errors;browser.close()
        finally:server.shutdown();server.server_close()
    print('Environments modal UI OK: native presets, disabled skills, partial preload, save/reload, polling preserves draft, failed save retains form, cloning, logs, mobile.')


if __name__=='__main__':main()
