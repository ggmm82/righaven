#!/usr/bin/env python3
"""Real xterm.js browser: ANSI, direct typing, Enter/Tab/arrows/Ctrl+C and resize."""
import argparse,base64,json,subprocess,tempfile,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--screenshots-dir',type=Path);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=args.node_modules.resolve();assets=args.assets.resolve()
    clients={};closed_clients=set();delayed=[False];start_entered=threading.Event();start_release=threading.Event()
    raw=bytearray(b'\x1b[31mCLI pronta\x1b[0m\r\nrighaven$ ');inputs=[];sizes=[];finished=[False]
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        (root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);');(root/'config.ts').write_text('export const getBackendBaseURL=()=>location.origin;')
        (root/'entry.tsx').write_text('import React from "react";import{createRoot}from"react-dom/client";import Page from '+json.dumps(str(repo/'frontend/environment-terminal-page.tsx'))+';createRoot(document.getElementById("root")!).render(<Page/>);')
        options={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':{'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts')}}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps(options)+');'],check=True)
        (root/'source.css').write_text('@import "tailwindcss";\n@source '+json.dumps(str(repo/'frontend/environment-terminal-page.tsx'))+';\n')
        subprocess.run(['node',str(modules/'@tailwindcss/cli/dist/index.mjs'),'-i',str(root/'source.css'),'-o',str(root/'app.css')],env={**__import__('os').environ,'NODE_PATH':str(modules)},check=True,capture_output=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,value,kind='application/json',status=200):
                self.send_response(status);self.send_header('Content-Type',kind);self.end_headers()
                try:self.wfile.write(value if isinstance(value,bytes) else value.encode())
                except (BrokenPipeError,ConnectionResetError):pass
            def session(self,identifier):return clients[identifier]
            def do_GET(self):
                from urllib.parse import urlsplit,parse_qs
                path=urlsplit(self.path).path
                if path.endswith('/status'):
                    cursor=int(parse_qs(urlsplit(self.path).query).get('after',['0'])[0]);time.sleep(.02)
                    return self.send(json.dumps({**self.session(path.split('/')[-2]),'output_base64':base64.b64encode(raw[cursor:]).decode(),'cursor':len(raw),'output_end':len(raw),'reset':False}))
                files={'/rh-terminal/xterm.js':assets/'@xterm/xterm/lib/xterm.js','/rh-terminal/addon-fit.js':assets/'@xterm/addon-fit/lib/addon-fit.js','/rh-terminal/xterm.css':assets/'@xterm/xterm/css/xterm.css','/app.js':root/'app.js','/app.css':root/'app.css'}
                if path in files:return self.send(files[path].read_bytes(),'text/css' if path.endswith('.css') else 'text/javascript')
                self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><div id="root"></div><script src="/app.js"></script>','text/html')
            def do_POST(self):
                value=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}')
                if '/terminal-clients/' in self.path and self.path.endswith('/close'):
                    identifier=self.path.split('/')[-2];closed_clients.add(identifier)
                    if identifier in clients:clients[identifier]['finished']=True
                    return self.send('{"accepted":true}')
                if self.path.endswith('/terminal'):
                    identifier=value['client_id']
                    if delayed[0]:start_entered.set();start_release.wait(5)
                    clients[identifier]={'id':identifier,'profile':'documenti','finished':identifier in closed_clients,'limits':{'cpus':.125,'memory_mib':128}}
                    return self.send(json.dumps(self.session(identifier)),status=201)
                if self.path.endswith('/input'):inputs.append(value['text'])
                if self.path.endswith('/resize'):sizes.append(value)
                self.send('{"accepted":true}')
            def do_DELETE(self):clients[self.path.split('/')[-1]]['finished']=True;self.send('{"accepted":true}')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox']);context=browser.new_context(viewport={'width':1200,'height':800});page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/terminal?environment=documenti')
                expect(page.locator('.xterm-screen')).to_be_visible()
                expect(page.locator('.xterm-rows')).to_contain_text('CLI pronta')
                textarea=page.locator('.xterm-helper-textarea');textarea.focus();textarea.press_sequentially('echo test',delay=20)
                textarea.press('Enter');textarea.press('ArrowUp');textarea.press('Tab');textarea.press('Control+c')
                until=time.monotonic()+5
                while time.monotonic()<until and '\x03' not in ''.join(inputs):page.wait_for_timeout(50)
                typed=''.join(inputs);assert 'echo test\r' in typed,repr(typed);assert '\x1b[A' in typed,repr(typed);assert '\t' in typed and '\x03' in typed,repr(typed)
                assert sizes and sizes[-1]['cols']>40,sizes
                first=sizes[-1];page.set_viewport_size({'width':900,'height':620})
                until=time.monotonic()+5
                while time.monotonic()<until and sizes[-1]==first:page.wait_for_timeout(50)
                assert sizes[-1]!=first,sizes
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                if args.screenshots_dir:
                    args.screenshots_dir.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(args.screenshots_dir/'terminal-desktop.png'),full_page=True)
                first_id=next(iter(clients))
                second=page.context.new_page();second.add_init_script('navigator.sendBeacon=()=>false');second.goto(f'http://127.0.0.1:{server.server_port}/terminal?environment=documenti')
                expect(second.get_by_role('status')).to_contain_text('Connesso')
                second_id=next(k for k in clients if k!=first_id);second.close(run_before_unload=True)
                until=time.monotonic()+5
                while time.monotonic()<until and second_id not in closed_clients:page.wait_for_timeout(50)
                assert clients[second_id]['finished'],'Closed page did not close its session'
                assert not clients[first_id]['finished'],'Closing one page killed a different terminal'
                delayed[0]=True;third=page.context.new_page();third.goto(f'http://127.0.0.1:{server.server_port}/terminal?environment=documenti')
                assert start_entered.wait(5),'Delayed start did not reach the server'
                third.close(run_before_unload=True)
                until=time.monotonic()+5
                while time.monotonic()<until and len(closed_clients)<2:page.wait_for_timeout(50)
                start_release.set();until=time.monotonic()+5
                while time.monotonic()<until and len(clients)<3:page.wait_for_timeout(50)
                assert len(clients)==3 and len(closed_clients)==2,'Close-before-response was not delivered'
                late=next(v for k,v in clients.items() if k not in (first_id,second_id))
                assert late['finished'],'Late start survived the page that opened it'
                page.get_by_role('button',name='Termina sessione',exact=True).click()
                expect(page.get_by_role('status')).to_contain_text('Sessione terminata · risorse liberate')
                assert not errors,errors;browser.close()
        finally:server.shutdown();server.server_close()
    print('Real xterm browser OK: separate full-window terminal, ANSI rendering, direct key input, Enter, history arrows, Tab, Ctrl+C, resize, independent page ownership, pagehide close, close-before-start-response and confirmed session termination.')


if __name__=='__main__':main()
