"""Exercise the real browser adapter destination picker and acknowledged saves."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright,expect

bridge=Path(__file__).resolve().parents[1].joinpath('righaven/editor-bridge.js').read_bytes()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/bridge.js':body=bridge;mime='application/javascript'
        elif self.path=='/app':body=b'<script src="/bridge.js"></script><input type="file">';mime='text/html'
        else:
            body=b'''<iframe src="/app"></iframe><script>
            window.saves=[];window.selected=[];window.messages=[];
            addEventListener('message',e=>{messages.push(e.data);if(e.data.type==='rh-editor-save'){saves.push(e.data);e.source.postMessage({type:'rh-editor-saved',requestId:e.data.requestId,error:window.rejectSave?'Fixture: disk full':undefined},location.origin);}if(e.data.type==='rh-editor-select')selected.push(e.data.name);});
            </script>''';mime='text/html'
        self.send_response(200);self.send_header('Content-Type',mime);self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/')
    frame=page.frames[1]
    page.evaluate("""()=>document.querySelector('iframe').contentWindow.postMessage({type:'rh-editor-files',files:[{name:'source.docx',bytes:new Uint8Array([1]).buffer}],manifest:[{name:'source.docx'},{name:'other.docx'}],fileBase:'/files/'},location.origin)""")
    frame.evaluate("""()=>{window.saved=showSaveFilePicker({suggestedName:'report.docx'}).then(async h=>{let s=await h.createWritable();await s.write('abcd');await s.write({type:'seek',position:1});await s.write('X');await s.write({type:'truncate',size:3});await s.close();});}""")
    frame.get_by_role('button',name='Chat files (server)',exact=True).click();frame.evaluate('()=>window.saved')
    assert page.evaluate('()=>new TextDecoder().decode(saves[0].bytes)')=='aXc'
    assert page.evaluate('saves.length')==1
    frame.evaluate("""()=>{window.saved=showSaveFilePicker({suggestedName:'local.txt'}).then(async h=>{let s=await h.createWritable();await s.write('local bytes');await s.close();});}""")
    with page.expect_download() as download:frame.get_by_role('button',name='This device',exact=True).click()
    assert download.value.suggested_filename=='local.txt';assert Path(download.value.path()).read_text()=='local bytes'
    assert page.evaluate('saves.length')==1
    frame.evaluate("document.querySelector('input').click()")
    frame.locator('select').select_option('other.docx');frame.get_by_role('button',name='Chat files (server)',exact=True).click()
    page.wait_for_function("selected[0]==='other.docx'")
    frame.evaluate("document.querySelector('input').click()")
    with page.expect_file_chooser():frame.get_by_role('button',name='This device',exact=True).click()
    page.evaluate("""()=>{window.rejectSave=true;document.querySelector('iframe').contentWindow.postMessage({type:'rh-editor-files',files:[{name:'recovery.ecproj',bytes:new ArrayBuffer(0)}]},location.origin);}""")
    frame.evaluate("""()=>{window.effectcraft={execute:async()=>({}),saveToBrowser:async()=>{},readFile:()=>new TextEncoder().encode('{}')};const banner=document.createElement('div');banner.id='device-lost';document.body.append(banner);}""")
    page.wait_for_function("messages.some(m=>m.type==='rh-editor-device-lost'&&m.error?.includes('Recovery save was not confirmed'))")
    assert not page.evaluate("messages.some(m=>m.type==='rh-editor-device-lost'&&m.error?.includes('Your current project was saved'))")
    browser.close()
server.shutdown()
print('Browser adapter: server saves, local downloads, server opens and local file chooser passed.')
