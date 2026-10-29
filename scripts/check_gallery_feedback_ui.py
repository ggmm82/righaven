#!/usr/bin/env python3
"""Browser test of reviews backed by real persistent feedback storage."""
import argparse,json,subprocess,tempfile,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=args.node_modules.resolve()
    from righaven import state,gallery,gallery_feedback
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);previous=state.STATE;state.STATE=root/'state'
        pack=dict(gallery.get_pack('skill-d2'));pack.update(id='review-fixture',author='publisher',version='1.0.0');gallery.publish_pack(pack)
        (root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);')
        entry=root/'entry.tsx';entry.write_text('import React from "react";import{createRoot}from"react-dom/client";import Page from '+json.dumps(str(repo/'frontend/gallery-feedback.tsx'))+';createRoot(document.getElementById("root")!).render(<Page base="/api/v1/gallery" pack="review-fixture" version="1.0.0" locale="en"/>);')
        build='require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps({'entryPoints':[str(entry)],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':{'@/core/api/fetcher':str(root/'fetch.ts')}})+');';subprocess.run(['node','-e',build],check=True)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,value,kind='application/json',code=200):
                self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(value if isinstance(value,bytes) else value.encode())
            def do_GET(self):
                parts=urlsplit(self.path);params=parse_qs(parts.query)
                if '/feedback' in parts.path:
                    data=gallery_feedback.list_feedback('review-fixture','reader',params.get('version',[None])[0],int(params.get('offset',[0])[0]))
                    return self.send(json.dumps(data))
                if parts.path=='/app.js':return self.send((root/'app.js').read_bytes(),'text/javascript')
                self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script src="/app.js"></script>','text/html')
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}')
                try:
                    if self.path.endswith('/report'):
                        gallery_feedback.report(self.path.split('/')[-2],'reader',body['reason']);return self.send('{}')
                    data=gallery_feedback.write('review-fixture',body['version'],'reader',body['body'],body.get('score'),body.get('parent'));self.send(json.dumps(data),code=201)
                except ValueError as error:self.send(json.dumps({'detail':str(error)}),code=422)
            def do_DELETE(self):gallery_feedback.remove(self.path.rsplit('/',1)[-1],'reader');self.send('{}')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':420,'height':850});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.get_by_text('No reviews for this version',exact=False)).to_be_visible()
                page.get_by_role('combobox',name='Rating',exact=True).select_option('4');page.get_by_role('textbox',name='Your experience').fill('Good diagrams; needs a clearer guide');page.get_by_role('button',name='Post',exact=True).click()
                expect(page.get_by_text('★ 4.0 / 5 · 1 reviews',exact=False)).to_be_visible()
                page.get_by_role('button',name='Edit review').click();page.get_by_role('combobox',name='Rating',exact=True).select_option('5');page.get_by_role('textbox',name='Your experience').fill('The improved guide solved my problem');page.get_by_role('button',name='Post',exact=True).click()
                expect(page.get_by_text('★ 5.0 / 5 · 1 reviews',exact=False)).to_be_visible()
                review=gallery_feedback.list_feedback('review-fixture','publisher')['items'][0]
                gallery_feedback.write('review-fixture','1.0.0','publisher','Thanks for the feedback',parent=review['id'])
                page.reload();expect(page.get_by_text('Thanks for the feedback',exact=True)).to_be_visible();expect(page.get_by_text('Publisher',exact=False).first).to_be_visible()
                page.get_by_role('button',name='Report',exact=True).click();page.get_by_role('textbox',name='Report reason').fill('Please check this response');page.get_by_role('button',name='Send to moderator').click()
                expect(page.get_by_role('textbox',name='Report reason')).to_have_count(0);assert gallery_feedback.reports()[0]['reports']==1
                page.get_by_role('button',name='Reply',exact=True).click();page.get_by_role('textbox',name='Your experience').fill('A follow-up comment');page.get_by_role('button',name='Post',exact=True).click();expect(page.get_by_text('A follow-up comment',exact=True)).to_be_visible()
                assert not errors,errors
                browser.close()
            print('Gallery review UI passed: rating update, version label, publisher reply, report and threaded comment; persistent real storage')
        finally:server.shutdown();server.server_close();state.STATE=previous


if __name__=='__main__':main()
