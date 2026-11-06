"""Real prepared notebook HTTP/edit/kernel-WebSocket/cleanup acceptance."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import uuid
import httpx
from righaven import editor_documents as docs,editor_runtime as runtimes,state


def browser_proxy(service,root):
    """Run the actual authenticated proxy against the live notebook UI.

    Only the fixture identity/thread store are simulated. HTTP, WebSockets,
    native editor routes, CSRF echo, notebook JavaScript and kernel are real.
    """
    import socket,threading
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import FastAPI,Request
    from fastapi.responses import JSONResponse
    from app.gateway.authz import AuthContext
    from righaven_core.runtime.user_context import set_current_user,reset_current_user
    from righaven.editor_proxy import router
    from playwright.sync_api import sync_playwright
    import uvicorn
    app=FastAPI();app.include_router(router)
    @app.middleware('http')
    async def owner(request:Request,call_next):
        if request.headers.get('Authorization'):return JSONResponse({'detail':'Internal notebook tokens are not RigHaven PATs'},status_code=401)
        user=SimpleNamespace(id='acceptance',system_role='user')
        request.state.auth=AuthContext(user,['threads:read','threads:write'])
        if request.method in ('POST','PUT','PATCH','DELETE') and request.headers.get('X-CSRF-Token')!='editor-csrf-fixture':
            return JSONResponse({'detail':'Missing fixture CSRF echo'},status_code=403)
        token=set_current_user(user)
        try:return await call_next(request)
        finally:reset_current_user(token)
    paths=SimpleNamespace(sandbox_user_data_dir=lambda thread,user_id:root)
    store=SimpleNamespace(check_access=AsyncMock(side_effect=lambda thread,user,require_existing=False:thread=='conversation' and user=='acceptance'))
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen();port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
    worker=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
    with patch('app.gateway.deps.get_thread_store',return_value=store),patch('righaven.collaboration_routes.get_paths',return_value=paths),patch('righaven.capability_policy.native_policy',return_value={'allowed':['jupyter']}):
        worker.start()
        try:
            deadline=time.monotonic()+10
            while not server.started:
                assert time.monotonic()<deadline;time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                context=browser.new_context();origin=f'http://127.0.0.1:{port}'
                context.add_cookies([{'name':'csrf_token','value':'editor-csrf-fixture','url':origin}])
                page=context.new_page();errors=[];console=[];page.on('pageerror',lambda e:errors.append(e.stack or str(e)));page.on('console',lambda message:console.append(message.text) if message.type=='error' else None)
                prefix=service.document['project_root']+'/' if callable(getattr(service,'public',None)) and service.document.get('mode')=='project' else ''
                page.goto(origin+service.public()['url'] if callable(getattr(service,'public',None)) else origin+service.proxy+'lab/tree/test.ipynb')
                devtools=context.new_cdp_session(page)
                def evaluate(expression):
                    result=devtools.send('Runtime.evaluate',{'expression':'Promise.race([Promise.resolve().then(()=>('+expression+')),new Promise((_,reject)=>setTimeout(()=>reject(Error("Browser action timed out")),30000))])','returnByValue':True,'awaitPromise':True,'allowUnsafeEvalBlockedByCSP':True})
                    assert not result.get('exceptionDetails'),result.get('exceptionDetails')
                    return result.get('result',{}).get('value')
                print("Lab loaded; waiting for notebook",flush=True)
                deadline=time.monotonic()+90
                while not evaluate('Boolean(window.jupyterapp?.shell?.currentWidget?.content?.activeCell)'):
                    assert time.monotonic()<deadline,{'errors':errors,'console':console};time.sleep(.2)
                evaluate("(()=>{const w=jupyterapp.shell.currentWidget;window.rhNotebookReady=false;Promise.all([w.context.ready,w.sessionContext.ready]).then(()=>window.rhNotebookReady=true);return true;})()")
                deadline=time.monotonic()+45
                while not evaluate('window.rhNotebookReady'):
                    if page.locator('.jp-Dialog-content select').count():
                        selector=page.locator('.jp-Dialog-content select').first
                        values=selector.locator('option').evaluate_all('(items)=>items.map(o=>({value:o.value,text:o.textContent}))')
                        kernel=next((item['value'] for item in values if 'Python' in item['text']),None)
                        if kernel is not None:selector.select_option(kernel)
                    if page.locator('.jp-Dialog-button.jp-mod-accept').count():page.locator('.jp-Dialog-button.jp-mod-accept').first.click()
                    assert time.monotonic()<deadline,page.locator('body').inner_text()[-3000:]
                    time.sleep(.2)
                print("Notebook ready; executing code",flush=True)
                evaluate("(async()=>{await jupyterapp.commands.execute('notebook:insert-cell-below');jupyterapp.shell.currentWidget.content.activeCell.model.sharedModel.setSource('21 * 2');void jupyterapp.commands.execute('notebook:run-cell');return true;})()")
                deadline=time.monotonic()+45
                while '42' not in (page.locator('.jp-OutputArea-output').all_text_contents()):
                    if page.locator('.jp-Dialog-button.jp-mod-accept').count():page.locator('.jp-Dialog-button.jp-mod-accept').first.click()
                    if time.monotonic()>=deadline:
                        page.screenshot(path='/tmp/righaven-editor-lab-failure.png')
                        raise AssertionError({'body':page.locator('body').inner_text()[-4000:],'errors':errors,'console':console,'context':evaluate('JSON.stringify(jupyterapp.shell.currentWidget.sessionContext?.session?.model)')})
                    time.sleep(.2)
                print("Code executed; saving",flush=True)
                evaluate("jupyterapp.commands.execute('docmanager:save').then(()=>true)")
                # Downloads must keep attachment headers and work as native
                # browser downloads through the authenticated proxy.
                with page.expect_download() as download:
                    evaluate("(()=>{const a=document.createElement('a');a.href='"+service.proxy+"files/"+prefix+"test.ipynb?download=1';a.download='test.ipynb';document.body.append(a);a.click();return true;})()")
                assert download.value.suggested_filename=='test.ipynb',download.value.suggested_filename
                assert download.value.failure() is None
                print("Browser download passed; opening Python script",flush=True)
                import zipfile
                wheel=root/'outputs/rh_editor_fixture-0.0.0-py3-none-any.whl'
                with zipfile.ZipFile(wheel,'w') as archive:
                    archive.writestr('rh_editor_fixture.py','value=42\n')
                    archive.writestr('rh_editor_fixture-0.0.0.dist-info/METADATA','Metadata-Version: 2.1\nName: rh-editor-fixture\nVersion: 0.0.0\n')
                    archive.writestr('rh_editor_fixture-0.0.0.dist-info/WHEEL','Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                    archive.writestr('rh_editor_fixture-0.0.0.dist-info/RECORD','')
                script_code="import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', 'rh_editor_fixture-0.0.0-py3-none-any.whl'], check=True, capture_output=True)\nfrom rh_editor_fixture import value\nprint(value)\n"
                if prefix:
                    inputs=root/'uploads';inputs.mkdir(exist_ok=True);(inputs/'editor-path-fixture.txt').write_text('42')
                    script_code=script_code.replace('print(value)',"from pathlib import Path\nassert Path('/mnt/user-data/uploads/editor-path-fixture.txt').read_text() == str(value)\nprint(value)")
                script_url=origin+service.proxy+'api/contents/'+prefix+'script.py'
                response=context.request.put(script_url,headers={'Origin':origin,'X-CSRF-Token':'editor-csrf-fixture'},data={'type':'file','format':'text','content':script_code})
                assert response.ok,response.text()
                evaluate("jupyterapp.commands.execute('docmanager:open',{path:"+json.dumps(prefix+'script.py')+"}).then(()=>true)")
                deadline=time.monotonic()+30
                while not evaluate("Boolean(jupyterapp.shell.currentWidget?.context?.path==="+json.dumps(prefix+'script.py')+")"):
                    assert time.monotonic()<deadline;time.sleep(.2)
                # Run a script using the native Lab file editor + console. This
                # exercises the user-facing action, not a surrogate REST eval.
                evaluate("(()=>{window.rhConsoleReady=false;jupyterapp.commands.execute('fileeditor:create-console').then(()=>window.rhConsoleReady=true);return true;})()")
                deadline=time.monotonic()+30
                while not evaluate('window.rhConsoleReady'):
                    if page.locator('.jp-Dialog-content select').count():
                        selector=page.locator('.jp-Dialog-content select').first
                        values=selector.locator('option').evaluate_all('(items)=>items.map(o=>({value:o.value,text:o.textContent}))')
                        kernel=next((item['value'] for item in values if 'Python' in item['text']),None)
                        if kernel is not None:selector.select_option(kernel)
                    if page.locator('.jp-Dialog-button.jp-mod-accept').count():page.locator('.jp-Dialog-button.jp-mod-accept').first.click()
                    assert time.monotonic()<deadline,page.locator('body').inner_text()[-2000:];time.sleep(.2)
                evaluate("jupyterapp.commands.execute('docmanager:open',{path:"+json.dumps(prefix+'script.py')+"}).then(()=>true)")
                # Console creation resolves before its optional kernel dialog
                # has fully settled. Complete the same first-use selection a
                # user sees before trying to focus the file editor again.
                for _ in range(15):
                    if page.get_by_role('dialog').count():
                        print('Console dialog: '+page.get_by_role('dialog').first.inner_text(),flush=True)
                        select=page.get_by_role('dialog').locator('select')
                        if select.count():
                            values=select.first.locator('option').evaluate_all('(items)=>items.map(o=>({value:o.value,text:o.textContent}))')
                            kernel=next((item['value'] for item in values if 'Python' in item['text']),None)
                            if kernel is not None:select.first.select_option(kernel)
                        buttons=page.get_by_role('dialog').first.get_by_role('button',name='Select',exact=True)
                        if buttons.count():buttons.click()
                        else:page.get_by_role('dialog').first.get_by_role('button').last.click()
                    page.wait_for_timeout(200)
                page.locator('[role=tab][data-type=document-title]').filter(has_text='script.py').click()
                deadline=time.monotonic()+30
                while not evaluate("jupyterapp.commands.isEnabled('fileeditor:run-all')"):
                    assert time.monotonic()<deadline;time.sleep(.2)
                evaluate("(()=>{void jupyterapp.commands.execute('fileeditor:run-all');return true;})()")
                deadline=time.monotonic()+30
                while not any('42' in text for text in page.locator('.jp-CodeConsole .jp-OutputArea-output').all_text_contents()):
                    if page.locator('.jp-Dialog-button.jp-mod-accept').count():page.locator('.jp-Dialog-button.jp-mod-accept').first.click()
                    assert time.monotonic()<deadline,page.locator('body').inner_text()[-2000:];time.sleep(.2)
                response=context.request.get(script_url);assert response.ok and response.json()['content']==script_code,response.text()
                evaluate("(()=>{window.postMessage({type:'rh-lab-terminal'},location.origin);return true;})()")
                deadline=time.monotonic()+30
                while not page.locator('.jp-Terminal').count():
                    assert time.monotonic()<deadline,page.locator('body').inner_text()[-2000:];time.sleep(.2)
                terminals=context.request.get(origin+service.proxy+'api/terminals')
                assert terminals.ok and terminals.json(),terminals.text()
                for terminal in terminals.json():
                    stopped=context.request.delete(origin+service.proxy+'api/terminals/'+terminal['name'],headers={'Origin':origin,'X-CSRF-Token':'editor-csrf-fixture'})
                    assert stopped.ok,stopped.text()
                assert not errors,{'errors':errors,'console':console}
                browser.close()
            print('PASS: real JupyterLab notebook execution, writable project, Python editor/console and browser download through owner proxy')
        finally:server.should_exit=True;worker.join(10);sock.close()


def main():
    with tempfile.TemporaryDirectory(prefix='rh-editor-service-') as temporary:
        root=Path(temporary);state.STATE=root/'state';state.STATE.mkdir();(state.STATE/'installation-id').write_text(uuid.uuid4().hex);(root/'outputs').mkdir()
        notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','language':'python','display_name':'Python 3'}},'cells':[{'cell_type':'markdown','id':'intro','metadata':{},'source':['Original notebook']}]}
        (root/'outputs/test.ipynb').write_text(json.dumps(notebook));document=docs.start(root,'/mnt/user-data/outputs/test.ipynb','jupyter',['jupyter'],direct=True);service=None
        with patch('righaven.environment_runtime.ensure',return_value={'id':'acceptance-notebook','image_id':os.getenv('RIGHAVEN_EDITOR_TEST_IMAGE','python:3.12-slim-bookworm')}),patch('righaven.environment_runtime.release_claim'),patch('righaven.docker_runtime.host_path',side_effect=lambda p:str(Path(p).resolve())):
            try:
                service=runtimes.start(root,document['id'],'acceptance','conversation',['jupyter']);deadline=time.monotonic()+900;last=''
                while service.state not in ('failed','ready'):
                    current=service.public()
                    if current['message']!=last:print(current['message'],flush=True);last=current['message']
                    if time.monotonic()>deadline:raise AssertionError('Interactive preparation timed out')
                    time.sleep(1)
                assert service.state=='ready',service.error
                assert service.public()['interface_version'],'Notebook interface version must be observed from the running program'
                headers={'Authorization':'token '+service.token}
                notebook_path='api/contents/'+(document['project_root']+'/' if document.get('mode')=='project' else '')+'test.ipynb'
                with httpx.Client(base_url=service.target+service.proxy,headers=headers,trust_env=False,timeout=30) as client:
                    response=client.get(notebook_path);assert response.status_code==200,response.text
                    model=response.json();model['content']['cells'][0]['source']=['Edited in the prepared notebook service']
                    response=client.put(notebook_path,json={'type':'notebook','content':model['content']});assert response.status_code==200,response.text
                    source=client.get(notebook_path).json()['content']['cells'][0]['source']
                    assert (''.join(source) if isinstance(source,list) else source)=='Edited in the prepared notebook service'
                    response=client.post('api/kernels',json={'name':'python3'});assert response.status_code==201,response.text;kernel_id=response.json()['id']
                    async def execute():
                        from websockets.asyncio.client import connect
                        async with connect(service.target.replace('http:','ws:',1)+service.proxy+f'api/kernels/{kernel_id}/channels',additional_headers=headers,origin=service.target,proxy=None,open_timeout=30) as ws:
                            mid=uuid.uuid4().hex
                            await ws.send(json.dumps({'header':{'msg_id':mid,'username':'acceptance','session':'acceptance','msg_type':'execute_request','version':'5.3'},'parent_header':{},'metadata':{},'channel':'shell','content':{'code':'2 + 2','silent':False,'store_history':False,'user_expressions':{},'allow_stdin':False,'stop_on_error':True}}))
                            for _ in range(40):
                                value=json.loads(await asyncio.wait_for(ws.recv(),30))
                                if value.get('parent_header',{}).get('msg_id')==mid and value.get('msg_type')=='execute_result':assert value['content']['data']['text/plain']=='4';return
                            raise AssertionError('No notebook execution result over WebSocket')
                    asyncio.run(execute());client.delete('api/kernels/'+kernel_id)
                browser_proxy(service,root)
                service.cancel.set();deadline=time.monotonic()+30
                while not service.closed:
                    assert time.monotonic()<deadline,'Editor did not release its container';time.sleep(.2)
                assert service.state=='stopped',service.error;draft=docs.get(root,document['id'],['jupyter']);assert draft['revision']==1,draft
                saved=json.loads((root/'outputs/test.ipynb').read_text());source=saved['cells'][0]['source']
                assert (''.join(source) if isinstance(source,list) else source)=='Edited in the prepared notebook service'
                assert any(output.get('data',{}).get('text/plain') in ('42',['42']) for cell in saved['cells'] for output in cell.get('outputs',[])),saved
                print('PASS: real notebook read/edit/save, Python kernel, direct chat persistence and runtime cleanup')
            finally:
                if service:service.cancel.set()

if __name__=='__main__':main()
