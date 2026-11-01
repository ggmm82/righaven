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
from righaven import journeys,projects,recipes,state
from playwright.sync_api import sync_playwright,expect


SKILLS=['skill-harness','skill-duckdb','skill-data-pipeline']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=Path(args.node_modules).resolve()
    with tempfile.TemporaryDirectory() as directory,patch.object(state,'STATE',Path(directory)/'state'):
        root=Path(directory);workspace=root/'work';workspace.mkdir()
        (root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);')
        (root/'config.ts').write_text('export function getBackendBaseURL(){return ""}')
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:"it-IT"}}')
        (root/'router.ts').write_text('export function useRouter(){return {push:(url:string)=>{window.location.href=url}}}')
        (root/'threads.ts').write_text('export async function createThread(id:string){return window.fetch("/api/threads",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({thread_id:id})}).then(r=>r.json())}')
        entry='''import React from 'react';import{createRoot}from'react-dom/client';import Recipes from PAGE;import{ProjectJourney,useJourney}from PANEL;
function Journey(){const id=location.pathname.split('/').pop()!;const state=useJourney(id);return <ProjectJourney threadId={id} state={state}/>;}
createRoot(document.getElementById('root')!).render(location.pathname.includes('/chats/')?<Journey/>:<Recipes/>);'''
        (root/'entry.tsx').write_text(entry.replace('PAGE',json.dumps(str(repo/'frontend/recipes-page.tsx'))).replace('PANEL',json.dumps(str(repo/'frontend/project-journey.tsx'))))
        aliases={'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts'),'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/i18n/ui-text':str(repo/'frontend/ui-text.ts'),'@/core/threads/api':str(root/'threads.ts'),'next/navigation':str(root/'router.ts')}
        build={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps(build)+')'],check=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,body,kind='application/json',code=200):
                self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body if isinstance(body,bytes) else body.encode())
            def do_GET(self):
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
                if self.path.endswith('/decision'):
                    value=journeys.decide(workspace,body['stage_id'],None,body['expected_revision'],body['note'],body['action']);return self.send(json.dumps({'journey':value}))
                if self.path=='/api/harness/recipes':
                    return self.send(json.dumps({'recipe':recipes.card(recipes.create('owner',{k:v for k,v in body.items() if k!='expected_revision'},SKILLS),'it','owner')}))
                return self.send('{}',code=404)
            def do_PUT(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
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
                    assert not errors,errors
                    page.close()
                # Recipe editor: the user composes skills, environment and phases into a new recipe, then starts it.
                page=browser.new_page(viewport={'width':1200,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/recipes')
                expect(page.get_by_test_id('recipe-vocabulary')).to_contain_text('Skill · come si lavora')
                page.get_by_role('button',name='Nuova ricetta',exact=True).click()
                editor=page.get_by_test_id('recipe-editor')
                editor.get_by_label('Titolo',exact=True).fill('Dashboard demo')
                editor.get_by_label('Quando usarla',exact=True).fill('Per mostrare un’idea con dati di esempio')
                editor.get_by_label('Cosa produce, in breve',exact=True).fill('Una dashboard semplice con dati sintetici')
                editor.get_by_label('duckdb',exact=False).check()
                editor.get_by_label('Ambiente',exact=True).select_option('dati')
                expect(editor.get_by_test_id('recipe-tools')).to_contain_text('duckdb, jupyter')
                editor.get_by_label('Titolo fase 1',exact=True).fill('Indicatori')
                editor.get_by_label('Risultato fase 1',exact=True).fill('Misure e dimensioni concordate')
                editor.get_by_role('button',name='Aggiungi fase',exact=True).click()
                editor.get_by_label('Titolo fase 2',exact=True).fill('Dashboard')
                editor.get_by_label('Risultato fase 2',exact=True).fill('Report consultabile')
                editor.get_by_test_id('recipe-phase').nth(1).get_by_label('chiede approvazione').uncheck()
                editor.get_by_label('Cosa allega l’utente (obbligatorio)',exact=True).fill('Elenco degli indicatori')
                editor.get_by_label('Cosa si ottiene (obbligatorio)',exact=True).fill('Dashboard HTML con i sorgenti')
                editor.get_by_role('button',name='Salva ricetta',exact=True).click()
                mine=page.locator('[data-testid^="recipe-dashboard-demo"]')
                expect(mine).to_contain_text('tua')
                expect(mine.get_by_test_id(re.compile('recipe-blocks-'))).to_contain_text('duckdb')
                expect(mine).to_contain_text('automatica')
                mine.get_by_role('button',name='Duplica',exact=True).click()
                expect(page.get_by_test_id('recipe-editor').get_by_label('Titolo',exact=True)).to_have_value('Copia di Dashboard demo')
                page.get_by_test_id('recipe-editor').get_by_role('button',name='Annulla',exact=True).click()
                assert not errors,errors
                page.close()
                browser.close()
            print('Guided UI OK: desktop/mobile, saved native thread, inline owner approval, skip/resume, recipe editor and duplicate')
        finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
