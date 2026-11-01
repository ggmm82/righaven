#!/usr/bin/env python3
"""Browser contract: outcome intake -> saved native thread -> reload -> phase approval.

HTTP fixtures exercise real React overlays and the journey storage engine.
Native auth/ownership are separately checked by test_journey_routes in Gateway CI.
"""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import journeys,projects,recipes,state
from playwright.sync_api import sync_playwright,expect


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
        entry='''import React from 'react';import{createRoot}from'react-dom/client';import Recipes from PAGE;import{ProjectJourney}from PANEL;
createRoot(document.getElementById('root')!).render(location.pathname.includes('/chats/')?<ProjectJourney threadId={location.pathname.split('/').pop()!}/>:<Recipes/>);'''
        (root/'entry.tsx').write_text(entry.replace('PAGE',json.dumps(str(repo/'frontend/recipes-page.tsx'))).replace('PANEL',json.dumps(str(repo/'frontend/project-journey.tsx'))))
        aliases={'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts'),'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/i18n/ui-text':str(repo/'frontend/ui-text.ts'),'@/core/threads/api':str(root/'threads.ts'),'next/navigation':str(root/'router.ts')}
        build={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps(build)+')'],check=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,body,kind='application/json',code=200):
                self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body if isinstance(body,bytes) else body.encode())
            def do_GET(self):
                if self.path.startswith('/api/harness/recipes'):return self.send(json.dumps({'recipes':recipes.catalog('it')}))
                if self.path.endswith('/harness-journey'):return self.send(json.dumps({'journey':journeys.view(workspace)}))
                if self.path=='/app.js':return self.send((root/'app.js').read_bytes(),'text/javascript')
                return self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script src="/app.js"></script>','text/html')
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or '{}')
                if self.path=='/api/threads':return self.send(json.dumps({'thread_id':body['thread_id']}))
                if self.path.endswith('/decision'):
                    value=journeys.decide(workspace,body['stage_id'],body['approve'],body['expected_revision'],body['note']);return self.send(json.dumps({'journey':value}))
                return self.send('{}',code=404)
            def do_PUT(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                value=journeys.start(workspace,body['recipe_id'],body['answers'],body['expected_revision']);return self.send(json.dumps({'journey':value}))
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
                    panel=page.get_by_test_id('project-journey');expect(panel).to_be_visible();panel.locator('summary').click()
                    expect(panel).to_contain_text('senza connessioni reali')
                    page.reload();expect(panel).to_be_visible()
                    projects.create_plan(workspace,'Catalogo',[{'id':'catalog','agent':'workspace','goal':'Read docs','depends_on':[]}])
                    artifact=workspace/'catalog.md';artifact.write_text('Schema and documented relationships')
                    current=journeys.view(workspace);journeys.record(workspace,'understand',[str(artifact)],['catalog'],'Catalogo con provenienza pronto per la revisione',current['revision'])
                    page.reload();panel.locator('summary').click()
                    expect(panel.get_by_role('link',name='catalog.md')).to_be_visible()
                    panel.get_by_role('button',name='Approva questa fase',exact=True).click()
                    expect(panel.locator('summary')).to_contain_text('1/7')
                    page.reload();expect(panel.locator('summary')).to_contain_text('1/7')
                    assert not errors,errors
                    page.close()
                browser.close()
            print('Guided UI OK: desktop/mobile, optional choices, saved native thread, reload, evidence links and owner approval')
        finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
