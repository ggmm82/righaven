"""Real editor UI against draft storage, optionally with upstream WASM applications."""
import argparse
import hashlib
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit,parse_qs,unquote
import zipfile
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright,expect,TimeoutError as BrowserTimeout
from righaven import editor_documents as docs,editor_assets as assets,editor_catalog as catalog,state,project_files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);parser.add_argument('--craft',action='store_true');parser.add_argument('--effect',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];modules=args.node_modules.resolve()
    with tempfile.TemporaryDirectory(prefix='rh-editor-browser-') as temporary:
        folder=Path(temporary);workspace=folder/'workspace';(workspace/'outputs').mkdir(parents=True);state.STATE=folder/'state';state.STATE.mkdir()
        (workspace/'outputs/report.md').write_text('Original source');(workspace/'outputs/word.txt').write_text('RigHaven original')
        from PIL import Image
        Image.new('RGB',(32,32),(30,100,190)).save(workspace/'outputs/photo.png')
        for name,code in {'fetch.ts':'export const fetch=(...args:Parameters<typeof globalThis.fetch>)=>globalThis.fetch(...args);','hooks.ts':'export const useI18n=()=>({locale:"it-IT"});','config.ts':'export const getBackendBaseURL=()=>"";','viewer.ts':'export const buildArtifactViewerURL=({filepath,threadId})=>"/artifacts/view?"+new URLSearchParams({path:filepath,thread_id:threadId});'}.items():(folder/name).write_text(code)
        (folder/'entry.jsx').write_text('import React from "react";import{createRoot}from"react-dom/client";import Editor from '+json.dumps(str(root/'frontend/editor-page.tsx'))+';import {ProjectFiles} from '+json.dumps(str(root/'frontend/project-files.tsx'))+';createRoot(document.getElementById("root")).render(location.pathname==="/browse"?<ProjectFiles threadId="fixture"/>:<Editor/>);')
        aliases={'@/components/workspace/artifacts/editor-launcher':str(root/'frontend/editor-launcher.tsx'),'@/core/api/fetcher':str(folder/'fetch.ts'),'@/core/i18n/hooks':str(folder/'hooks.ts'),'@/core/config':str(folder/'config.ts'),'@/core/artifacts/viewer':str(folder/'viewer.ts')}
        bundle={'entryPoints':[str(folder/'entry.jsx')],'bundle':True,'outfile':str(folder/'app.js'),'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases,'define':{'process.env.NODE_ENV':'"production"'}}
        subprocess.run(['node','-e',f'require({json.dumps(str(modules/"esbuild"))}).buildSync({json.dumps(bundle)})'],check=True)
        (folder/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><style>html,body,#root,main{height:100%;margin:0}main{display:flex;flex-direction:column}main>div:last-child{display:flex;flex:1;min-height:0}aside{width:200px}section{flex:1}iframe{height:100%;width:100%;border:0}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>')
        allowed=['wordcraft','photocraft']
        if args.craft or args.effect:allowed.append('effectcraft')
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self,*_):pass
            def reply(self,value,code=200):
                data=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def content(self,data,mime='application/octet-stream'):
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass
            def dispatch(self):
                parsed=urlsplit(self.path);path=unquote(parsed.path);query=parse_qs(parsed.query);prefix='/api/threads/fixture/editors';tail=path.removeprefix(prefix).strip('/');parts=tail.split('/');sid=parts[0] if tail else ''
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                try:
                    if path=='/api/harness/environments':return self.reply({'environments':[{'name':'python-env','display_name':'Python ready','runtime':{'status':'ready'}},{'name':'not-prepared','display_name':'Not prepared','runtime':{'status':'on_demand'}}]})
                    if path=='/api/threads/fixture/project-files':return self.reply(project_files.listing(workspace,query.get('path',[''])[0],query.get('query',[''])[0],query.get('role',['all'])[0],int(query.get('offset',['0'])[0])))
                    if not path.startswith(prefix):
                        if self.command=='GET' and (path.startswith('/edit') or path=='/browse'):return self.content((folder/'index.html').read_bytes(),'text/html')
                        return super().do_GET()
                    if not sid and self.command=='GET':
                        choices=[{**row,'source_role':'selected'} for row in catalog.candidates(docs.metadata(workspace,query['session'][0],allowed)['entry'],allowed)] if query.get('session') else docs.associations(workspace,query['path'][0],allowed) if query.get('path') else []
                        return self.reply({'editors':choices,'available_editors':[row for row in catalog.definitions() if not row['tool'] or row['tool'] in allowed],'sessions':docs.listing(workspace,allowed)})
                    if not sid and self.command=='POST':
                        value=json.loads(body);return self.reply(docs.start(workspace,value['path'],value['editor'],allowed,value.get('entry',''),value.get('manual',False),value.get('direct',False)))
                    if self.command=='GET' and len(parts)==1:return self.reply(docs.get(workspace,sid,allowed))
                    if parts[-1]=='open-with' and self.command=='POST':
                        value=json.loads(body);return self.reply(docs.open_with(workspace,sid,value['editor'],allowed,value.get('manual',False)))
                    session=docs.get(workspace,sid,allowed)
                    if len(parts)>=3 and parts[1]=='files':
                        name='/'.join(parts[2:])
                        if self.command=='GET':return self.content(docs.file(workspace,sid,name,allowed).read_bytes())
                        return self.reply(docs.save(workspace,sid,name,body,int(query['expected_revision'][0]),allowed,query.get('entry')==['true']))
                    if parts[-1]=='publish':return self.reply(docs.publish(workspace,sid,json.loads(body)['expected_revision'],allowed))
                    if parts[-1]=='prepare':return self.reply(assets.request(session['editor'],session['editor_version']))
                    if parts[-1]=='package':return self.reply(assets.status(session['editor'],session['editor_version']))
                    if parts[-1]=='bridge.js':return self.content((root/'righaven/editor-bridge.js').read_bytes(),'application/javascript')
                    if len(parts)>=3 and parts[1]=='app':
                        name='/'.join(parts[2:]);file=assets.file(session['editor'],session['editor_version'],name)
                        if name=='index.html':return self.content(file.read_text().replace('<head>','<head><script src="../bridge.js"></script>',1).encode(),'text/html')
                        return self.content(file.read_bytes(),'application/wasm' if name.endswith('.wasm') else 'application/javascript' if name.endswith('.js') else 'application/octet-stream')
                    return self.reply({'detail':'Not found'},404)
                except (ValueError,KeyError) as error:return self.reply({'detail':str(error)},409)
            do_GET=dispatch;do_POST=dispatch;do_PUT=dispatch
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(folder)));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--enable-webgl'])
                page=browser.new_page(viewport={'width':1440,'height':1000});base=f'http://127.0.0.1:{server.server_port}';errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                (workspace/'outputs/related.sql').write_text('SELECT 1;')
                metadata=workspace/'.righaven-project/project.json';metadata.parent.mkdir(exist_ok=True)
                metadata.write_text(json.dumps({'steps':[{'attempts':[{'delivery_record':{'files':[{'path':'/mnt/user-data/outputs/report.md','role':'export','sha256':hashlib.sha256(b'Original source').hexdigest()},{'path':'/mnt/user-data/outputs/related.sql','role':'editable_source','sha256':hashlib.sha256(b'SELECT 1;').hexdigest()}]}}]}]}))
                page.goto(base+'/browse');page.get_by_role('button',name='File',exact=True).click()
                file_dialog=page.get_by_role('dialog',name='File del progetto');expect(file_dialog).to_be_visible()
                folder_button=file_dialog.get_by_role('button',name='▸ outputs',exact=True)
                folder_button.click();expect(folder_button).to_have_attribute('aria-pressed','true')
                expect(file_dialog.get_by_role('button',name='report.md',exact=True)).to_have_count(0)
                folder_button.dblclick()
                row=file_dialog.get_by_role('list',name='File del progetto').get_by_role('listitem').filter(has=page.get_by_role('button',name='report.md',exact=True))
                row.get_by_role('button',name='report.md',exact=True).click()
                expect(row.get_by_test_id('editor-launcher')).to_have_count(0)
                expect(row).to_contain_text('Modificato');expect(row).to_contain_text('15 B')
                with page.expect_popup() as preview:row.get_by_role('button',name='report.md',exact=True).dblclick()
                assert '/artifacts/view?' in preview.value.url;preview.value.close()
                row.get_by_role('button',name='Apri con',exact=True).click();expect(row.get_by_test_id('editor-launcher')).to_be_visible()
                expect(row.get_by_test_id('editor-launcher').get_by_role('option',name='Sorgente · related.sql · Text and code')).to_have_count(1)
                with page.expect_popup() as popup:row.get_by_test_id('editor-launcher').get_by_role('link').click()
                opened=popup.value;expect(opened.locator('.cm-content')).to_contain_text('Original source');opened.close()
                file_dialog.get_by_label('Cerca nei file').fill('report');expect(file_dialog.get_by_role('button',name='outputs/report.md',exact=True)).to_be_visible()
                file_dialog.get_by_label('Cerca nei file').fill('missing-no-file');expect(file_dialog.get_by_text('Nessun file in questa vista.',exact=True)).to_be_visible()
                file_dialog.get_by_role('button',name='Bozze editor',exact=True).click();expect(file_dialog.get_by_role('link',name='report.md',exact=True)).to_be_visible()
                file_dialog.get_by_role('button',name='Chiudi',exact=True).click();metadata.unlink()
                legacy=docs.start(workspace,'/mnt/user-data/outputs/report.md','text',allowed)
                page.goto(base+'/edit?thread=fixture&session='+legacy['id']);expect(page.locator('.cm-content')).to_contain_text('Original source')
                other=browser.new_page();other.goto(page.url);expect(other.locator('.cm-content')).to_contain_text('Original source')
                page.locator('.cm-content').fill('Revised source');page.get_by_role('button',name='Salva file',exact=True).click();expect(page.get_by_role('status')).to_contain_text('Bozza salvata')
                other.locator('.cm-content').fill('Conflicting revision');other.get_by_role('button',name='Salva file',exact=True).click();expect(other.get_by_role('alert')).to_contain_text('Draft changed')
                with other.expect_download() as recovered:other.get_by_role('button',name='Scarica copia',exact=True).click()
                assert Path(recovered.value.path()).read_text()=='Conflicting revision'
                other.close()
                page.get_by_role('button',name='Cambia editor',exact=True).click()
                launcher=page.get_by_test_id('editor-launcher')
                launcher.get_by_role('combobox').select_option(label='PhotoCraft · compatibilità da verificare')
                expect(launcher).to_contain_text('Formato non dichiarato')
                launcher.get_by_role('combobox').select_option(index=0)
                with page.expect_popup() as changed:launcher.get_by_role('link',name='Apri editor',exact=False).click()
                clone=changed.value;expect(clone.locator('.cm-content')).to_contain_text('Revised source')
                assert clone.url!=page.url;assert not (workspace/'.righaven-project/source-edits.json').exists();clone.close()
                page.reload();expect(page.locator('.cm-content')).to_contain_text('Revised source');page.get_by_role('button',name='Pubblica revisione',exact=True).click();page.get_by_role('button',name='File e dettagli',exact=True).click();expect(page.get_by_role('link',name='Apri revisione 1',exact=True)).to_be_visible()
                assert (workspace/'outputs/report.md').read_text()=='Original source';assert list((workspace/'outputs/source-revisions').rglob('report.md'))[0].read_text()=='Revised source'
                assert not errors,errors
                page.goto(base+'/edit?thread=fixture&path=/mnt/user-data/outputs/report.md&editor=text');expect(page.locator('.cm-content')).to_contain_text('Original source')
                expect(page.get_by_role('button',name='Pubblica revisione',exact=True)).to_have_count(0)
                expect(page.locator('aside')).to_have_count(0)
                page.locator('.cm-content').fill('Saved directly');page.get_by_role('button',name='Salva file',exact=True).click();expect(page.get_by_role('status')).to_contain_text('File salvato')
                assert (workspace/'outputs/report.md').read_text()=='Saved directly'
                page.get_by_role('button',name='File e dettagli',exact=True).click();expect(page.locator('aside')).to_be_visible()
                page.get_by_role('button',name='Terminale',exact=True).click()
                terminal=page.get_by_role('region',name='Ambiente del terminale')
                expect(terminal).to_be_visible()
                expect(terminal.get_by_role('option')).to_have_count(1)
                expect(terminal.get_by_role('option')).to_have_text('Python ready')
                expect(terminal.get_by_role('link',name='Apri terminale',exact=False)).to_have_attribute('href',__import__('re').compile(r'/terminal\?thread=fixture&editor=[a-f0-9]{32}&environment=python-env'))
                terminal.get_by_role('button',name='Chiudi',exact=True).click()
                if args.craft:
                    for app,path,suffix in [('wordcraft','word.txt','.docx'),('photocraft','photo.png','.psd')]:
                        page.goto(base+f'/edit?thread=fixture&path=/mnt/user-data/outputs/{path}&editor={app}');expect(page.locator('iframe')).to_be_visible(timeout=120000)
                        child=page.frame_locator('iframe');expect(child.locator('canvas')).to_be_visible(timeout=60000);page.wait_for_timeout(12000)
                        page.wait_for_timeout(10000)
                        child.locator('canvas').click(position={'x':550,'y':310})
                        if app=='wordcraft':
                            page.screenshot(path='/tmp/righaven-editor-before-first-edit.png');page.keyboard.press('Control+End');page.keyboard.type(' changed in RigHaven',delay=60);page.wait_for_timeout(1000);page.screenshot(path='/tmp/righaven-editor-after-first-edit.png')
                        page.keyboard.press('Control+s');choose=page.frame_locator('iframe').get_by_role('button',name='Chat files (server)',exact=True)
                        try:choose.click(timeout=4000)
                        except BrowserTimeout:pass
                        expect(page.get_by_role('status')).to_contain_text('File salvato',timeout=30000)
                        sid=parse_qs(urlsplit(page.url).query)['session'][0];session=docs.get(workspace,sid,allowed);assert session['entry'].endswith(suffix),session
                        native=docs.file(workspace,sid,session['entry'],allowed)
                        if app=='wordcraft':
                            with zipfile.ZipFile(native) as archive:text=''.join(ET.fromstring(archive.read('word/document.xml')).itertext());assert 'changed in RigHaven' in text,text
                        else:assert native.read_bytes().startswith(b'8BPS')
                        page.reload();expect(page.locator('iframe')).to_be_visible(timeout=30000)
                        expect(page.frame_locator('iframe').locator('canvas')).to_be_visible(timeout=30000);page.wait_for_timeout(12000)
                        page.wait_for_timeout(10000)
                        page.frame_locator('iframe').locator('canvas').click(position={'x':550,'y':310})
                        if app=='wordcraft':
                            page.screenshot(path='/tmp/righaven-editor-before-reopen-edit.png');page.keyboard.press('Control+End');page.keyboard.type(' reopened',delay=60);page.wait_for_timeout(1000);page.screenshot(path='/tmp/righaven-editor-after-reopen-edit.png')
                        page.keyboard.press('Control+s');choose=page.frame_locator('iframe').get_by_role('button',name='Chat files (server)',exact=True)
                        try:choose.click(timeout=4000)
                        except BrowserTimeout:pass
                        expect(page.get_by_role('status')).to_contain_text('File salvato',timeout=30000)
                        reopened=docs.get(workspace,sid,allowed);assert reopened['revision']>session['revision']
                        if app=='wordcraft':
                            with zipfile.ZipFile(docs.file(workspace,sid,reopened['entry'],allowed)) as archive:text=''.join(ET.fromstring(archive.read('word/document.xml')).itertext());assert 'changed in RigHaven' in text and 'reopened' in text,text
                        print('PASS: real '+app+' automatically opens, edits, saves and reopens its native source',flush=True)
                if args.craft or args.effect:
                    effect=workspace/'outputs/effect-project';(effect/'A').mkdir(parents=True);(effect/'B').mkdir()
                    svg=lambda color:('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="'+color+'"/></svg>').encode()
                    (effect/'seed.svg').write_bytes(svg('red'));(effect/'A/logo.svg').write_bytes(svg('red'));(effect/'B/logo.svg').write_bytes(svg('blue'))
                    (workspace/'uploads').mkdir(exist_ok=True);(workspace/'uploads/logo.svg').write_bytes(svg('blue'))
                    page.goto(base+'/edit?thread=fixture&path=/mnt/user-data/outputs/effect-project/seed.svg&editor=effectcraft')
                    expect(page.locator('iframe')).to_be_visible(timeout=120000)
                    child=next(frame for frame in page.frames if frame.parent_frame==page.main_frame)
                    child.wait_for_function('Boolean(window.effectcraftLoad?.readyMs)',timeout=90000)
                    page.get_by_role('button',name='Schermo intero',exact=True).click()
                    page.wait_for_function("document.fullscreenElement?.tagName==='IFRAME'")
                    page.evaluate('document.exitFullscreen()')
                    source=child.evaluate("""async ([a,b])=>{
                        const paths=[];
                        paths.push(await effectcraft.addFile(new File([a],'first.svg')));
                        paths.push(await effectcraft.addFile(new File([b],'second.svg')));
                        await new Promise(r=>setTimeout(r,1500));
                        await effectcraft.saveToBrowser('/seed.ecproj');
                        const scene=JSON.parse(new TextDecoder().decode(effectcraft.readFile('/seed.ecproj')));
                        const ids=Object.values(scene.items).filter(item=>item.kind.type==='Footage').map(item=>item.id);
                        await effectcraft.execute('file.interpretFootage',{items:ids,colorProfile:'rec709',linearLight:true});
                        await effectcraft.saveToBrowser('/seed.ecproj');
                        return {paths,bytes:Array.from(effectcraft.readFile('/seed.ecproj'))};
                    }""",[svg('red').decode(),svg('blue').decode()])
                    project=json.loads(bytes(source['bytes']));mapping={**dict(zip(source['paths'],['A/logo.svg','/mnt/user-data/uploads/logo.svg'])),'/seed.svg':'seed.svg'}
                    from righaven.source_packages import references
                    count=0
                    for owner,key,ref in references(project):
                        if ref in mapping:owner[key]=mapping[ref];count+=1
                    assert count>=2,project
                    (effect/'scene.ecproj').write_text(json.dumps(project))
                    page.goto(base+'/edit?thread=fixture&path=/mnt/user-data/outputs/effect-project/scene.ecproj&editor=effectcraft')
                    expect(page.locator('iframe')).to_be_visible(timeout=60000)
                    child=next(frame for frame in page.frames if frame.parent_frame==page.main_frame)
                    child.wait_for_function('Boolean(window.effectcraftLoad?.readyMs)',timeout=90000)
                    try:child.wait_for_function("effectcraft.files().filter(f=>f.path.includes('righaven-')).length>=2",timeout=30000)
                    except BrowserTimeout:
                        print('Effect startup diagnostic: '+json.dumps({'alerts':page.get_by_role('alert').all_text_contents(),'files':child.evaluate('effectcraft.files()'),'load':child.evaluate('effectcraftLoad')}),flush=True)
                        page.screenshot(path='/tmp/righaven-editor-effect-failure.png');raise
                    page.wait_for_timeout(1500)
                    if page.get_by_role('alert').count():print('Effect errors: '+str(page.get_by_role('alert').all_text_contents()),flush=True)
                    proof=child.evaluate("effectcraft.execute('footage.check',{wait:true})")
                    if proof['missing']:
                        debug=child.evaluate("async()=>{await effectcraft.saveToBrowser('/debug.ecproj');const project=JSON.parse(new TextDecoder().decode(effectcraft.readFile('/debug.ecproj')));return {version:effectcraft.info().version,files:effectcraft.files(),footage:Object.values(project.items).filter(item=>item.kind.type==='Footage').map(item=>({name:item.name,path:item.kind.path,missing:item.kind.missing}))};}")
                        print('Effect diagnostic: '+json.dumps(debug),flush=True)
                    assert proof['missing']==0,proof
                    info=child.evaluate('effectcraft.info()')
                    assert info['storage']['backend']=='memory',info
                    assert info.get('backend')=='Gl',info
                    assert child.evaluate("effectcraft.execute('prefs.get',{key:'memory.layerCacheMb'})")==64
                    assert child.evaluate("effectcraft.execute('prefs.get',{key:'memory.mediaCacheMb'})")==64
                    assert child.evaluate("effectcraft.execute('prefs.get',{key:'memory.previewCacheMb'})")==128
                    assert not child.evaluate('Boolean(navigator.gpu)')
                    print('PASS: EffectCraft uses WebGL, isolated memory storage and 64/64/128 MB cache budgets',flush=True)
                    page.get_by_role('button',name='Salva nella chat',exact=True).click()
                    expect(page.get_by_role('status')).to_contain_text('File salvato',timeout=30000)
                    stored=json.loads((effect/'scene.ecproj').read_text());refs=[ref for _,_,ref in references(stored)]
                    assert 'A/logo.svg' in refs and '/mnt/user-data/uploads/logo.svg' in refs,refs
                    assert not any('righaven-' in ref for ref in refs),refs
                    for key,item in project['items'].items():
                        if item['kind']['type']=='Footage':
                            self_kind=stored['items'][key]['kind']
                            assert self_kind.get('color_profile')==item['kind'].get('color_profile'),self_kind
                            assert self_kind.get('linear_light')==item['kind'].get('linear_light'),self_kind
                            assert stored['items'][key]['name']==item['name']
                    assert not page.get_by_role('alert').count(),page.get_by_role('alert').all_text_contents()
                    print('PASS: real EffectCraft project opens both distinct same-named SVG assets, checks native footage and saves relative references directly',flush=True)
                    first=next(iter(stored['items']))
                    child.evaluate("id=>effectcraft.execute('project.rename',{item:Number(id),name:'Recovered after device loss'})",first)
                    child.evaluate("()=>{const banner=document.createElement('div');banner.id='device-lost';document.body.append(banner);}")
                    expect(page.get_by_role('alert')).to_contain_text('Your current project was saved to the chat',timeout=30000)
                    recovered=json.loads((effect/'scene.ecproj').read_text())
                    assert recovered['items'][first]['name']=='Recovered after device loss'
                    print('PASS: simulated graphics-device loss saves current unsaved edits and waits for server acknowledgement',flush=True)

                browser.close()
        finally:server.shutdown();server.server_close();thread.join()
    print('PASS: project file folders, search, open-with and drafts; editor UI save, conflict, reopen and immutable publication'+('; real WordCraft DOCX and PhotoCraft PSD bridges' if args.craft else ''))

if __name__=='__main__':main()
