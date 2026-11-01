#!/usr/bin/env python3
"""Browser contract: outcome intake -> saved native thread -> reload -> phase approval.

HTTP fixtures exercise real React overlays and the journey storage engine.
Native auth/ownership are separately checked by test_journey_routes in Gateway CI.
"""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import connections,journeys,projects,recipes,state
from playwright.sync_api import sync_playwright,expect


SKILLS=['skill-harness','skill-duckdb','skill-data-pipeline']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=Path(args.node_modules).resolve()
    import base64,os
    from cryptography.fernet import Fernet
    claims=base64.urlsafe_b64encode(json.dumps({'preferred_username':'marco@contoso.com'}).encode()).decode().rstrip('=')
    polls=[]
    def microsoft(url,data,timeout):
        class Reply:
            headers={'content-type':'application/json'}
            def __init__(self,code,body):self.status_code,self.body=code,body
            def json(self):return self.body
        if url.endswith('/devicecode'):return Reply(200,{'device_code':'D','user_code':'ABCD-EFGH','verification_uri':'https://microsoft.com/devicelogin','expires_in':900,'interval':1})
        if data.get('grant_type')=='refresh_token':return Reply(200,{'access_token':'AT','expires_in':3600})
        polls.append(1)
        return Reply(400,{'error':'authorization_pending'}) if len(polls)%2 else Reply(200,{'refresh_token':'RT-secret','id_token':'h.'+claims+'.s'})
    def azure(url,headers,timeout):
        class Reply:
            headers={'content-type':'application/json'}
            def __init__(self,body):self.status_code,self.body=200,body
            def json(self):return self.body
        if url.endswith('/subscriptions?api-version=2022-12-01'):return Reply({'value':[{'subscriptionId':'s1','displayName':'Produzione'}]})
        return Reply({'value':[{'name':'vendite/master'},{'name':'vendite/erp','location':'westeurope'},{'name':'vendite/hr','location':'westeurope'}]})
    with tempfile.TemporaryDirectory() as directory,patch.object(state,'STATE',Path(directory)/'state'),\
         patch.object(connections,'folder',side_effect=lambda user:(Path(directory)/'users'/user).mkdir(parents=True,exist_ok=True) or Path(directory)/'users'/user),\
         patch.dict(os.environ,{'RIGHAVEN_CREDENTIALS_KEY':Fernet.generate_key().decode()}),patch('httpx.post',side_effect=microsoft),patch('httpx.get',side_effect=azure):
        root=Path(directory);workspace=root/'work';workspace.mkdir()
        (root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);')
        (root/'config.ts').write_text('export function getBackendBaseURL(){return ""}')
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:"it-IT"}}')
        (root/'router.ts').write_text('export function useRouter(){return {push:(url:string)=>{window.location.href=url}}}')
        (root/'threads.ts').write_text('export async function createThread(id:string){return window.fetch("/api/threads",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({thread_id:id})}).then(r=>r.json())}')
        entry='''import React from 'react';import{createRoot}from'react-dom/client';import Recipes from PAGE;import Connections from CONNECTIONS;import{ProjectJourney,useJourney}from PANEL;
function Journey(){const id=location.pathname.split('/').pop()!;const state=useJourney(id);return <ProjectJourney threadId={id} state={state}/>;}
createRoot(document.getElementById('root')!).render(location.pathname.includes('/chats/')?<Journey/>:location.pathname==='/connections'?<Connections/>:<Recipes/>);'''
        (root/'entry.tsx').write_text(entry.replace('PAGE',json.dumps(str(repo/'frontend/recipes-page.tsx'))).replace('PANEL',json.dumps(str(repo/'frontend/project-journey.tsx')))
                                      .replace('CONNECTIONS',json.dumps(str(repo/'frontend/connections-page.tsx'))))
        aliases={'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts'),'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/i18n/ui-text':str(repo/'frontend/ui-text.ts'),'@/core/threads/api':str(root/'threads.ts'),'next/navigation':str(root/'router.ts')}
        build={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps(build)+')'],check=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,body,kind='application/json',code=200):
                self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body if isinstance(body,bytes) else body.encode())
            def do_GET(self):
                if self.path=='/api/harness/connections':return self.send(json.dumps({'connections':connections.listing('owner'),'kinds':list(connections.KINDS)}))
                if self.path=='/api/harness/access-catalog':return self.send(json.dumps({'providers':[]}))
                if self.path.startswith('/api/harness/recipes/editor/options'):
                    return self.send(json.dumps({'skills':[{'name':s,'description':'Metodo '+s,'kind':'method'} for s in SKILLS],
                                                 'environments':[{'id':'dati','name':'Dati e analisi','purpose':'Analisi','tools':['duckdb','jupyter','quarto','gridcraft'],'skills':[]}]}))
                if '/draft' in self.path:return self.send(json.dumps({'draft':recipes.draft(self.path.split('/')[4],'it','owner')}))
                if self.path.startswith('/api/harness/recipes'):return self.send(json.dumps({'recipes':recipes.catalog('it','owner'),'can_share':False}))
                if self.path.endswith('/harness-journey'):return self.send(json.dumps({'journey':journeys.view(workspace)}))
                if self.path=='/app.js':return self.send((root/'app.js').read_bytes(),'text/javascript')
                return self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script src="/app.js"></script>','text/html')
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or '{}')
                if self.path=='/api/threads':return self.send(json.dumps({'thread_id':body['thread_id']}))
                if self.path=='/api/harness/connections':return self.send(json.dumps(connections.save('owner',body)))
                if self.path.endswith('/sign-in'):return self.send(json.dumps(connections.sign_in('owner',self.path.split('/')[4])))
                if self.path.endswith('/sign-in/poll'):return self.send(json.dumps(connections.complete_sign_in('owner',self.path.split('/')[4])))
                if self.path.endswith('/databases'):return self.send(json.dumps(connections.databases('owner',self.path.split('/')[4])))
                if self.path.endswith('/decision'):
                    value=(journeys.decide_many(workspace,body['stage_ids'],body['action'],body['expected_revision'],body['note']) if body.get('stage_ids')
                           else journeys.decide(workspace,body['stage_id'],None,body['expected_revision'],body['note'],body['action']));return self.send(json.dumps({'journey':value}))
                if self.path=='/api/harness/recipes':
                    return self.send(json.dumps({'recipe':recipes.card(recipes.create('owner',{k:v for k,v in body.items() if k!='expected_revision'},SKILLS),'it','owner')}))
                return self.send('{}',code=404)
            def do_PUT(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                if self.path.startswith('/api/harness/connections/'):return self.send(json.dumps(connections.save('owner',body,self.path.split('/')[4])))
                value=journeys.start(workspace,body['recipe_id'],body['answers'],body['expected_revision'],journeys.definition(body['recipe_id'],'owner'));return self.send(json.dumps({'journey':value}))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--no-sandbox'])
                for width in (1200,390):
                    # Each viewport gets an independent workflow fixture.
                    for name in ('journey.json','project.json'):(workspace/'.righaven-project'/name).unlink(missing_ok=True)
                    page=browser.new_page(viewport={'width':width,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/recipes')
                    page.get_by_role('button',name='Usa questa ricetta',exact=True).click()
                    page.get_by_label('Cosa vuoi realizzare? Descrivilo con parole tue.',exact=True).fill('Dai documenti al catalogo, ai dati sintetici e al report vendite')
                    page.get_by_role('button',name='Avanti',exact=True).click()
                    page.get_by_role('button',name='Rivedi e avvia',exact=True).click()
                    page.get_by_role('button',name='Crea progetto guidato',exact=True).click()
                    page.wait_for_url('**/workspace/chats/*')
                    card=page.get_by_test_id('journey-card');panel=page.get_by_test_id('project-journey');expect(panel).to_be_visible()
                    expect(panel).to_contain_text('Pipeline dati end-to-end')
                    panel.get_by_role('button',name='Tutte le fasi',exact=True).click()
                    expect(card).to_contain_text('senza connessioni reali')
                    page.reload();expect(panel).to_be_visible()
                    projects.create_plan(workspace,'Catalogo',[{'id':'catalog','agent':'workspace','goal':'Read docs','depends_on':[]}])
                    artifact=workspace/'catalog.md';artifact.write_text('Schema and documented relationships')
                    current=journeys.view(workspace);journeys.record(workspace,'understand',[str(artifact)],['catalog'],'Catalogo con provenienza pronto per la revisione',current['revision'])
                    page.reload()
                    decision=page.get_by_test_id('journey-decision')
                    expect(decision).to_contain_text('Tocca a te')
                    expect(decision.get_by_role('link',name='catalog.md')).to_be_visible()
                    expect(decision.get_by_role('button',name='Chiedi correzioni',exact=True)).to_be_disabled()
                    decision.get_by_role('button',name='Approva fase',exact=True).click()
                    progress=page.get_by_test_id('journey-progress')
                    expect(progress).to_contain_text('1/7');expect(decision).to_have_count(0)
                    # A coordinator proposal to skip waits for the owner; the owner skips from the card.
                    current=journeys.view(workspace);journeys.record(workspace,'design',[],[],'Per una demo con dati di esempio non serve una progettazione separata',current['revision'],propose_skip=True)
                    page.reload();expect(decision).to_contain_text('propone di saltare')
                    decision.get_by_role('button',name='Salta fase',exact=True).click()
                    expect(progress).to_contain_text('2/7')
                    page.reload();expect(progress).to_contain_text('2/7')
                    panel.get_by_role('button',name='Tutte le fasi',exact=True).click()
                    phases=page.get_by_test_id('journey-phase')
                    expect(phases.nth(1)).to_contain_text('Saltata')
                    expect(phases.nth(2)).to_contain_text('senza approvazione')
                    phases.nth(1).get_by_role('button',name='Riprendi questa fase',exact=True).click()
                    expect(progress).to_contain_text('1/7')
                    expect(panel.get_by_test_id('journey-goal')).to_contain_text('Dai documenti al catalogo')
                    # The team compares the goal with every phase and proposes the skips in one turn; one answer settles them.
                    current=journeys.view(workspace)
                    for stage in ('pipeline','package'):
                        current=journeys.record(workspace,stage,[],[],'Per una demo con dati di esempio non serve',current['revision'],propose_skip=True)
                    page.reload()
                    proposals=page.get_by_test_id('journey-proposals')
                    expect(proposals).to_contain_text('propone di saltare 2 fasi')
                    proposals.get_by_role('button',name='Salta queste 2 fasi',exact=True).click()
                    expect(progress).to_contain_text('3/7');expect(proposals).to_have_count(0)
                    assert not errors,errors
                    page.close()
                # Personal Microsoft account: device code with MFA on Microsoft's page, then usable by SQL Server connections.
                page=browser.new_page(viewport={'width':390,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/connections')
                page.get_by_role('button',name='Nuova: Microsoft Entra ID',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Tipo di accesso',exact=True)).to_have_value('user')
                expect(form.get_by_label('Segreto client',exact=False)).to_have_count(0)
                form.get_by_label('Nome',exact=True).fill('Il mio account')
                form.get_by_role('button',name='Salva',exact=True).click()
                row=page.get_by_test_id('connection-il-mio-account')
                expect(row).to_contain_text('Accesso Microsoft da completare')
                row.get_by_role('button',name='Accedi con Microsoft',exact=True).click()
                signing=row.get_by_test_id('microsoft-sign-in')
                expect(signing).to_contain_text('ABCD-EFGH')
                expect(signing.get_by_role('link',name='https://microsoft.com/devicelogin')).to_be_visible()
                expect(signing).to_contain_text('Accesso completato: marco@contoso.com',timeout=10000)
                expect(row).to_contain_text('Account marco@contoso.com')
                assert 'RT-secret' not in json.dumps(connections.listing('owner'))
                # SQL Server with my Microsoft account: paste the connection string, sign in, pick the database from the list.
                page.get_by_role('button',name='Nuova: SQL Server / Azure SQL / Fabric',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Autenticazione',exact=True)).to_have_value('microsoft')
                form.get_by_label('Nome',exact=True).fill('Vendite Azure')
                form.get_by_label('Server, URL o stringa di connessione',exact=True).fill('Server=tcp:vendite.database.windows.net,1433;Initial Catalog=;User ID=marco@contoso.com;Encrypt=True;')
                form.get_by_label('Utente (email dell’account Microsoft)',exact=True).fill('marco@contoso.com')
                form.get_by_label('Confermo che l’account ha solo permessi di lettura').check()
                form.get_by_role('button',name='Salva',exact=True).click()
                sql=page.get_by_test_id('connection-vendite-azure')
                expect(sql).to_contain_text('vendite.database.windows.net:1433')
                expect(sql.get_by_role('button',name='Elenca database',exact=True)).to_be_disabled()
                sql.get_by_role('button',name='Accedi con Microsoft',exact=True).click()
                expect(sql.get_by_test_id('microsoft-sign-in')).to_contain_text('Accesso completato: marco@contoso.com',timeout=10000)
                sql.get_by_role('button',name='Elenca database',exact=True).click()
                listing=sql.get_by_test_id('database-list')
                expect(listing).to_contain_text('erp');expect(listing).not_to_contain_text('master')
                listing.get_by_role('listitem').filter(has_text='erp').get_by_role('button',name='Usa questo database').click()
                expect(sql).to_contain_text('vendite.database.windows.net:1433 / erp')
                assert connections._read('owner','vendite-azure')['refresh_token']=='RT-secret','choosing the database keeps the sign-in'
                assert not errors,errors
                page.close()
                # Recipe editor: the user composes skills, environment and phases into a new recipe, then starts it.
                page=browser.new_page(viewport={'width':1200,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/recipes')
                expect(page.get_by_test_id('recipe-vocabulary')).to_contain_text('Skill · come si lavora')
                page.get_by_role('button',name='Nuova ricetta',exact=True).click()
                editor=page.get_by_test_id('recipe-editor')
                editor.get_by_label('Nome della ricetta',exact=False).fill('Dashboard demo')
                editor.get_by_label('Che risultato produce',exact=False).fill('Una dashboard semplice con dati sintetici')
                editor.get_by_label('Quando conviene usarla',exact=False).fill('Per mostrare un’idea con dati di esempio')
                editor.get_by_label('Cosa si ottiene alla fine',exact=False).fill('Dashboard HTML con i sorgenti')
                editor.get_by_label('Cosa deve allegare chi la usa',exact=False).fill('Elenco degli indicatori')
                editor.get_by_role('button',name='Avanti',exact=True).click()
                editor.get_by_label('Nome fase 1',exact=True).fill('Indicatori')
                editor.get_by_label('Risultato fase 1',exact=True).fill('Misure e dimensioni concordate')
                editor.get_by_role('button',name='Aggiungi fase',exact=True).click()
                editor.get_by_label('Nome fase 2',exact=True).fill('Dashboard')
                editor.get_by_label('Risultato fase 2',exact=True).fill('Report consultabile')
                expect(editor.get_by_test_id('recipe-phase').nth(1).get_by_label('Mi fermo per l’approvazione')).not_to_be_checked()
                editor.get_by_role('button',name='Avanti',exact=True).click()
                editor.get_by_label('Dati e analisi',exact=False).check()
                expect(editor.get_by_test_id('recipe-tools')).to_contain_text('duckdb, jupyter')
                editor.get_by_text('Cambia le competenze (facoltativo)',exact=True).click()
                editor.get_by_label('duckdb',exact=False).check()
                editor.get_by_role('button',name='Avanti',exact=True).click()
                expect(editor.get_by_test_id('recipe-preview')).to_contain_text('Indicatori — Misure e dimensioni concordate')
                editor.get_by_role('button',name='Salva ricetta',exact=True).click()
                mine=page.locator('[data-testid^="recipe-dashboard-demo"]')
                expect(mine).to_contain_text('tua')
                expect(mine.get_by_test_id(re.compile('recipe-blocks-'))).to_contain_text('duckdb')
                expect(mine).to_contain_text('automatica')
                mine.get_by_role('button',name='Duplica',exact=True).click()
                expect(page.get_by_test_id('recipe-editor').get_by_label('Nome della ricetta',exact=False)).to_have_value('Copia di Dashboard demo')
                page.get_by_test_id('recipe-editor').get_by_role('button',name='Annulla',exact=True).click()
                assert not errors,errors
                page.close()
                browser.close()
            print('Guided UI OK: desktop/mobile, saved native thread, inline owner approval, skip/resume, personal Microsoft sign-in, recipe editor and duplicate')
        finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
