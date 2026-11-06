#!/usr/bin/env python3
"""Browser acceptance for pre-message connections, shared choices and source copies.
Uses the real components with declared HTTP fixtures; no external account or model.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);args=parser.parse_args()
    modules=args.node_modules.resolve();root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='rh-collaboration-ui-') as directory:
        folder=Path(directory)
        (folder/'fetch.ts').write_text('export const fetch=(...args:Parameters<typeof globalThis.fetch>)=>globalThis.fetch(...args);')
        (folder/'config.ts').write_text('export const getBackendBaseURL=()=>"";')
        (folder/'threads.ts').write_text('export const createThread=async(threadId)=>{const r=await fetch("/api/threads",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({thread_id:threadId})});if(!r.ok)throw Error("create failed");};')
        (folder/'hooks.ts').write_text('export const useI18n=()=>({locale:"it-IT"});')
        (folder/'viewer.ts').write_text('export const buildArtifactViewerURL=({filepath,threadId})=>"/artifacts/view?"+new URLSearchParams({path:filepath,thread_id:threadId});')
        entry='''import React from 'react';import {createRoot} from 'react-dom/client';
import {ChatConnections} from CONNECTIONS;
import {SharedMethod} from METHOD;
import {SourceCopyEditor} from EDITOR;
import {ProjectObjective} from OBJECTIVE;
import {useJourney} from JOURNEY;
function JourneyProbe(){const state=useJourney("fixture");return <p data-testid="guided-path-state">{state.journey?"guided":"open"}</p>}
const root=createRoot(document.getElementById('root'));window.resumes=0;window.objectiveChanges=0;addEventListener('righaven-objective-changed',()=>window.objectiveChanges++);
window.render=(busy=false)=>root.render(<main>
<ChatConnections threadId="fixture" disabled={busy} prepare={async()=>{const r=await fetch('/prepare',{method:'POST'});if(!r.ok)throw Error('prepare failed')}}/>
<SharedMethod threadId="fixture" busyTeam={busy} onContinue={()=>{window.resumes++}}/>
<SourceCopyEditor threadId="fixture" filepath="/mnt/user-data/outputs/report.md" content="Original" sha256={"a".repeat(64)} truncated={false} isMock={false}/>
<JourneyProbe/><ProjectObjective threadId="fixture" busyTeam={busy} onContinue={m=>{window.newGoal=m;window.resumes++}}/>
</main>);window.render();'''
        for key,value in [('CONNECTIONS',root/'frontend/chat-connections.tsx'),('METHOD',root/'frontend/shared-method.tsx'),('EDITOR',root/'core/frontend/src/components/workspace/artifacts/source-copy-editor.tsx'),('OBJECTIVE',root/'frontend/project-objective.tsx'),('JOURNEY',root/'frontend/project-journey.tsx')]:entry=entry.replace(key,json.dumps(str(value)))
        (folder/'entry.tsx').write_text(entry)
        subprocess.run([str(modules/'.bin/esbuild'),str(folder/'entry.tsx'),'--bundle','--jsx=automatic','--outfile='+str(folder/'app.js'),
            '--alias:react='+str(modules/'react'),'--alias:react-dom='+str(modules/'react-dom'),
            '--alias:@/core/api/fetcher='+str(folder/'fetch.ts'),'--alias:@/core/config='+str(folder/'config.ts'),'--alias:@/core/threads/api='+str(folder/'threads.ts'),
            '--alias:@/core/artifacts/viewer='+str(folder/'viewer.ts'),'--alias:@/core/i18n/hooks='+str(folder/'hooks.ts'),
            '--alias:@/core/i18n/ui-text='+str(root/'frontend/ui-text.ts'),
            '--alias:@/components/workspace/messages/project-connections='+str(root/'frontend/project-connections.tsx')],check=True,capture_output=True)
        (folder/'index.html').write_text('<html><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><div id="root"></div><script src="/app.js"></script></html>')
        state={}
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,value,status=200):
                self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(value).encode())
            def do_GET(self):
                if self.path=='/api/harness/connections':return self.reply({'connections':[{'id':'erp','name':'ERP','kind':'postgres','read_only':False,'write_enabled':True,'write_schema':'public'}]})
                if self.path.endswith('/harness-connections'):
                    if not state.get('prepared'):return self.reply({'detail':'No thread'},404)
                    return self.reply({'assigned':state.get('assigned',[])})
                if self.path.endswith('/harness-method'):return self.reply(state['method'])
                if self.path.endswith('/harness-journey'):return self.reply({'journey':None if state.get('objective') else {'revision':6,'created_at':'old-journey'}})
                if self.path.endswith('/harness-objective'):return self.reply(state.get('objective',{'signature':'c'*64,'goal':'Previous dashboard','guided':True,'can_change':True}))
                return super().do_GET()
            def do_PUT(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state['assigned']=[{'id':i,'name':'ERP','kind':'postgres','read_only':False,'write_schema':'public',
                                    'write':i in data.get('write',[]),'use':'destination' if i in data.get('write',[]) else 'unspecified',
                                    'deferred':i in data.get('deferred',[]),'fulfillment':'deferred' if i in data.get('deferred',[]) else 'pending'} for i in data['ids']]
                return self.reply({'assigned':state['assigned']})
            def do_POST(self):
                if self.path=='/prepare':state['prepare_called']=True;return self.reply({})
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path=='/api/threads':state['prepared']=True;state['thread_creations']=state.get('thread_creations',0)+1;return self.reply({})
                if self.path.endswith('/harness-objective'):
                    state['new_objective']=data
                    state['objective']={'signature':'d'*64,'goal':data['goal'],'guided':False,'can_change':True,'scope':{'parent':{'id':'old','goal':'Previous dashboard','product_path':'/mnt/user-data/outputs/dashboard.html','files':['/mnt/user-data/outputs/source.py'],'files_count':1},'ancestors':[]}}
                    return self.reply({'changed':True})
                if self.path.endswith('/choice'):
                    state['choices']+=1;state['last_choice']=data
                    decision={'method':'Method B','note':data['note'],'at':'2026-11-02T12:00:00Z'}
                    state['method'].update(decision=decision,history=[decision]);return self.reply(state['method'])
                if self.path.endswith('/harness-source-edits'):
                    state['edit']=data;return self.reply({'path':'/mnt/user-data/outputs/source-revisions/copy/report.md'})
                return self.reply({},404)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(folder)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                for width in (1280,390):
                    state.clear();state.update(choices=0,method={'signature':'b'*64,'strategy':{'method':'Method A','reason':'Initial proposal',
                        'alternatives':[{'method':'Method B','reason':'Different trade-off','status':'tested'}]},'decision':None,'history':[],'recipe_available':False,'recipe_stale':False})
                    page=browser.new_page(viewport={'width':width,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    page.get_by_test_id('chat-connections-button').click()
                    expect(page.get_by_role('dialog')).to_be_visible();page.get_by_label('ERP',exact=False).click()
                    expect(page.get_by_label('ERP',exact=False)).to_be_checked()
                    expect(page.get_by_role('status')).to_have_count(0)
                    expect(page.get_by_text('Salvato: il coordinatore vedrà queste connessioni dal prossimo turno.',exact=True)).to_be_visible()
                    page.get_by_test_id('write-consent-erp').get_by_role('checkbox').click()
                    expect(page.get_by_role('status')).to_contain_text('scrittura ancora da eseguire')
                    page.get_by_label('Rimanda la scrittura:',exact=False).click()
                    expect(page.get_by_role('status')).to_contain_text('rimandata da te; consegna locale')
                    assert state['assigned'][0]['deferred']
                    page.get_by_label('Rimanda la scrittura:',exact=False).click()
                    expect(page.get_by_role('status')).to_contain_text('scrittura ancora da eseguire')
                    page.get_by_role('button',name='Chiudi',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
                    expect(page.get_by_test_id('chat-connections-button')).to_contain_text('(1)')
                    assert state['prepare_called'] and state['thread_creations']==1
                    page.evaluate('window.render(true)');expect(page.get_by_role('button',name='Scegli e prosegui')).to_be_disabled()
                    page.evaluate('window.render(false)');page.get_by_label('Quale approccio vuoi provare?').select_option('1')
                    page.get_by_label('Indicazioni o vincoli aggiuntivi').fill('Keep the editable sources')
                    page.get_by_role('button',name='Scegli e prosegui').click()
                    expect(page.get_by_test_id('shared-method')).to_contain_text('La tua scelta: Method B')
                    assert state['choices']==1 and state['last_choice']['choice']==1
                    assert page.evaluate('window.resumes')==1
                    page.get_by_role('button',name='Modifica una copia').click()
                    page.get_by_label('Contenuto del sorgente').fill('Edited text')
                    page.get_by_role('button',name='Salva copia revisionata').click()
                    expect(page.get_by_role('link',name='Apri la copia')).to_have_attribute('href',__import__('re').compile('/artifacts/view\\?'))
                    assert state['edit']['expected_sha256']=='a'*64 and state['edit']['content']=='Edited text'
                    assert 'rigenerare le esportazioni' in page.get_by_test_id('source-copy-editor').inner_text()
                    state['method']['recipe_available']=True
                    expect(page.get_by_role('link',name='Rivedi e salva la ricetta')).to_have_attribute('href','/workspace/recipes?from_thread=fixture',timeout=10000)
                    page.get_by_label('Quale risultato vuoi ottenere adesso?').fill('Use this dashboard for a customer portal')
                    page.get_by_role('button',name='Avvia il nuovo obiettivo',exact=True).click()
                    expect(page.get_by_test_id('project-objective')).to_contain_text('Nuovo obiettivo salvato')
                    page.wait_for_function("window.newGoal==='Use this dashboard for a customer portal'")
                    expect(page.get_by_test_id('guided-path-state')).to_have_text('open')
                    assert page.evaluate('window.objectiveChanges')==1
                    page.get_by_text('Base e obiettivi precedenti',exact=True).click()
                    expect(page.get_by_role('link',name='Apri il risultato di partenza')).to_have_attribute('href',__import__('re').compile('dashboard.html'))
                    assert not errors,errors
                    page.close()
                browser.close()
        finally:server.shutdown();server.server_close();thread.join()
    print('Browser OK: pre-message connection consent, owner method choice and one resume, source-copy editing, private recipe review on desktop/mobile.')


if __name__=='__main__':main()
