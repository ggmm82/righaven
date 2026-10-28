#!/usr/bin/env python3
"""Exercise the real Excalidraw editor, explicit save, revisions and frame isolation."""
import argparse,json,subprocess,tempfile,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);parser.add_argument('--web',type=Path,required=True);parser.add_argument('--tool',choices=['excalidraw','bpmn'],default='excalidraw');parser.add_argument('--screenshots-dir',type=Path);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=args.node_modules.resolve();web=args.web.resolve()
    from acceptance_design import SAMPLES
    initial=json.loads(SAMPLES['excalidraw'][1]) if args.tool=='excalidraw' else SAMPLES['bpmn'][1];record={'id':'idea','title':'Idea e risultato','tool':args.tool,'revision':1,'source_path':'/mnt/user-data/workspace/model.'+args.tool,'actor':'team','state':'proposed','bindings':[{'element_id':'idea','step_id':'outline'}]}
    state={'record':record,'source':json.dumps(initial) if args.tool=='excalidraw' else initial,'posts':[]}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);(root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);');(root/'config.ts').write_text('export const getBackendBaseURL=()=>location.origin;')
        entry=root/'entry.tsx';entry.write_text('import React from "react";import{createRoot}from"react-dom/client";import{ProjectDesign}from'+json.dumps(str(repo/'frontend/project-design.tsx'))+';window.reviews=0;createRoot(document.getElementById("root")!).render(<ProjectDesign threadId="fixture" designs={'+json.dumps([record])+'} steps={[{id:"outline",goal:"Definire il risultato",status:"pending"}]} roles={[]} onReview={()=>window.reviews++}/>);')
        build="require("+json.dumps(str(modules/'esbuild'))+").buildSync("+json.dumps({'entryPoints':[str(entry)],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':{'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts')}})+");"
        subprocess.run(['node','-e',build],check=True)
        (root/'source.css').write_text('@import "tailwindcss";\n@source '+json.dumps(str(repo/'frontend/project-design.tsx'))+';\n')
        subprocess.run(['node',str(modules/'@tailwindcss/cli/dist/index.mjs'),'-i',str(root/'source.css'),'-o',str(root/'app.css')],env={**__import__('os').environ,'NODE_PATH':str(modules)},check=True,capture_output=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,body,kind='application/json',status=200):
                self.send_response(status);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body if isinstance(body,bytes) else body.encode())
            def do_GET(self):
                if self.path.startswith('/api/'):return self.send(json.dumps({**state['record'],'source':state['source']}))
                if self.path.startswith('/rh-design/'+args.tool+'/'):
                    file=(web/self.path.removeprefix('/rh-design/'+args.tool+'/')).resolve()
                    if not file.is_relative_to(web) or not file.is_file():return self.send('',status=404)
                    kind={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2'}.get(file.suffix,'application/octet-stream');return self.send(file.read_bytes(),kind)
                if self.path in ('/app.js','/app.css'):return self.send((root/self.path[1:]).read_bytes(),'text/javascript' if self.path.endswith('js') else 'text/css')
                return self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><main id="root" style="max-width:900px;margin:16px auto;padding:16px"></main><script src="/app.js"></script>','text/html')
            def do_POST(self):
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])));state['posts'].append(value)
                if value['revision']!=state['record']['revision']:return self.send('{"detail":"Ricarica la revisione corrente"}',status=409)
                state['source']=value['source'];state['record']={**state['record'],'revision':state['record']['revision']+1,'state':'changed','actor':'user'}
                return self.send(json.dumps({'design':state['record']}))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1100,'height':900});page.goto(f'http://127.0.0.1:{server.server_port}/')
                expect(page.get_by_test_id('project-design')).to_contain_text('Definire il risultato')
                frame=page.frame_locator('iframe');expect(frame.locator('.excalidraw' if args.tool=='excalidraw' else '.bjs-container')).to_be_visible(timeout=60000)
                page.evaluate("""()=>dispatchEvent(new MessageEvent('message',{source:document.querySelector('iframe').contentWindow,origin:'https://foreign.example',data:{type:'rh-design-save',document:{type:'excalidraw',elements:[]}}}))""")
                assert not state['posts'],'Foreign frame message was accepted'
                # A real SDK update followed by the user's explicit Save crosses the iframe bridge.
                model={**initial,'elements':[{**initial['elements'][0],'x':120,'version':2}]} if args.tool=='excalidraw' else initial.replace('Review','New review')
                page.locator('iframe').evaluate('(el,model)=>el.contentWindow.postMessage({type:"rh-design-load",document:model},location.origin)',model)
                if args.tool=='bpmn':expect(frame.get_by_text('New review',exact=True)).to_be_visible()
                frame.locator('#save').click();expect(page.get_by_text('Revisione 2',exact=False)).to_be_visible(timeout=15000)
                assert len(state['posts'])==1
                assert json.loads(state['source'])['elements'][0]['x']==120 if args.tool=='excalidraw' else 'New review' in state['source']
                assert page.evaluate('window.reviews')==0,'Saving started coordinator work'
                # A concurrent update keeps the user's draft and offers a concrete recovery.
                newer={**initial,'elements':[{**initial['elements'][0],'x':220,'version':3}]} if args.tool=='excalidraw' else initial.replace('Review','Server review')
                state['record']={**state['record'],'revision':3};state['source']=json.dumps(newer) if args.tool=='excalidraw' else newer
                frame.locator('#save').click();expect(page.get_by_role('alert')).to_contain_text('Ricarica')
                with page.expect_download() as pending:
                    page.get_by_role('button',name='Scarica bozza e ricarica').click()
                downloaded=pending.value
                draft=Path(downloaded.path()).read_text()
                assert json.loads(draft)['elements'][0]['x']==120 if args.tool=='excalidraw' else 'New review' in draft
                expect(page.get_by_text('Revisione 3',exact=False)).to_be_visible()
                for width in (1100,390):
                    page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Horizontal overflow'
                    if args.screenshots_dir:args.screenshots_dir.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(args.screenshots_dir/f'design-{args.tool}-{width}.png'),full_page=True)
                page.get_by_role('button',name='Chiedi alla squadra',exact=False).click();assert page.evaluate('window.reviews')==1
                browser.close()
        finally:server.shutdown()
    print('Design UI OK: native editor, immutable revision save, source download, mobile layout, foreign-frame rejection and explicit review action')


if __name__=='__main__':main()
