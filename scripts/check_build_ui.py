"""The real Overview displays a semantic product version, with source IDs in details."""
import argparse,json,subprocess,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from playwright.sync_api import sync_playwright,expect

parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='rh-overview-') as temporary:
    folder=Path(temporary)
    fixtures={'fetch.js':'export const fetch=(...args)=>globalThis.fetch(...args);','config.js':'export const getBackendBaseURL=()=>"";','i18n.js':'export const useI18n=()=>({locale:"it-IT"});','projects.js':'export const useProjects=()=>({data:[],isLoading:false,isError:false});','auth.js':'export const useAuth=()=>({user:{email:"fixture@example.test"}});','link.jsx':'import React from "react";export default function Link({children,...props}){return <a {...props}>{children}</a>;}' }
    for name,value in fixtures.items():(folder/name).write_text(value)
    aliases={'@/core/api/fetcher':str(folder/'fetch.js'),'@/core/config':str(folder/'config.js'),'@/core/i18n/hooks':str(folder/'i18n.js'),'@/core/projects/hooks':str(folder/'projects.js'),'@/core/auth/AuthProvider':str(folder/'auth.js'),'next/link':str(folder/'link.jsx')}
    (folder/'entry.jsx').write_text('import React from "react";import{createRoot}from"react-dom/client";import Overview from '+json.dumps(str(root/'core/frontend/src/app/workspace/page.tsx'))+';createRoot(document.getElementById("root")).render(<Overview/>);')
    options={'entryPoints':[str(folder/'entry.jsx')],'bundle':True,'outfile':str(folder/'app.js'),'jsx':'automatic','nodePaths':[str(args.node_modules.resolve())],'alias':aliases,'define':{'process.env.NODE_ENV':'"production"'}}
    subprocess.run(['node','-e',f'require({json.dumps(str(args.node_modules.resolve()/"esbuild"))}).buildSync({json.dumps(options)})'],check=True)
    (folder/'index.html').write_text('<html><body><div id="root"></div><script src="/app.js"></script></body></html>')
    class Handler(SimpleHTTPRequestHandler):
        version='0.7.5'
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/api/harness/build':
                data=json.dumps({'version':self.version,'commit':'abcdef123456','ref':'PR #19','local':False,'built_at':'2026-11-04T08:00Z'}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data);return
            super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(folder)));threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page()
            for version,label in [('0.7.5','Versione 0.7.5'),('0.7.6-rc.pr.19.123.1','Versione 0.7.6 · Anteprima PR #19')]:
                Handler.version=version;page.goto(f'http://127.0.0.1:{server.server_port}/')
                identity=page.get_by_test_id('build-identity');expect(identity.locator('span')).to_have_text(label)
                expect(identity.locator('details p')).not_to_be_visible();identity.get_by_text('Dettagli tecnici').click()
                expect(identity.locator('details p')).to_contain_text('abcdef123456');expect(identity.locator('details p')).to_contain_text(version)
            browser.close()
    finally:server.shutdown()
print('PASS: semantic release and preview labels; commit/build IDs only in technical details.')
