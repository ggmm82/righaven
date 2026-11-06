"""Interactive services on prepared software with owned writable project folders."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import select
import subprocess
import threading
import time
from . import state,editor_documents as documents
from .editor_catalog import editor

SESSIONS={}
LOCK=threading.RLock()


def interface(image,kind,progress,cancel=None,claim=None):
    from .docker_runtime import docker,base_arguments,remove
    from .resource_budget import BUDGET
    revision='interactive-v2-lab-4.6.5' if kind=='notebook' else 'interactive-v1'
    key=hashlib.sha256((image+':'+kind+':'+revision).encode()).hexdigest();tag='righaven-editor:'+key
    root=state.STATE/'editor-interfaces';root.mkdir(parents=True,exist_ok=True)
    with (root/(key+'.lock')).open('a') as lock:
        deadline=time.monotonic()+1800
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if cancel and cancel.is_set():raise ValueError('Editor preparation cancelled')
                if time.monotonic()>deadline:raise ValueError('Waiting for an identical interface timed out')
                progress('An identical interactive interface is already preparing');time.sleep(.5)
        inspected=subprocess.run(['docker','image','inspect',tag],capture_output=True,text=True)
        if inspected.returncode==0:
            from .editor_interface_cache import remember
            remember(key,tag,image,kind,packages=None,claim=claim)
            return tag
        packages=['python3-venv','python3-pip'] if kind=='notebook' else ['xvfb','openbox','x11vnc','novnc','websockify','libgl1-mesa-dri','dbus-x11']
        name='rh-editor-prepare-'+secrets.token_hex(8);resources=BUDGET.acquire(name,'build',timeout=120,cancel=cancel)
        args=base_arguments(name,resources);tmp=args.index('--tmpfs');del args[tmp:tmp+2]
        for cap in ('CHOWN','FOWNER','DAC_OVERRIDE','SETUID','SETGID'):args+=['--cap-add',cap]
        from .environment_runtime import installation
        args+=['--label','org.righaven.harness.installation='+installation(),'--user','0',image,'sh','-ec',
               'apt-get update && apt-get install -y --no-install-recommends '+' '.join(packages)+' && rm -rf /var/lib/apt/lists/*'+(' && python3 -m venv --system-site-packages /opt/righaven/jupyter-server && /opt/righaven/jupyter-server/bin/pip install --no-cache-dir jupyterlab==4.6.5 ipykernel==7.4.0 ipywidgets==8.1.9' if kind=='notebook' else '')]
        process=None
        try:
            progress('Installing interactive interface: '+', '.join(packages));output=bytearray()
            process=subprocess.Popen(['docker',*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            while process.poll() is None:
                if cancel and cancel.is_set():raise ValueError('Editor preparation cancelled; draft retained')
                if time.monotonic()>deadline:raise ValueError('Interactive preparation timed out')
                if select.select([process.stdout],[],[],1)[0]:
                    output.extend(os.read(process.stdout.fileno(),65536));output=output[-16000:]
                    lines=output.decode(errors='replace').strip().splitlines()
                    if lines:progress('Preparing interactive interface · '+lines[-1][:250])
            if process.returncode:raise ValueError('Interactive interface preparation failed: '+output.decode(errors='replace')[-1200:])
            docker('commit',name,tag,timeout=180)
            from .editor_interface_cache import remember
            remember(key,tag,image,kind,packages=packages,claim=claim)
            return tag
        finally:
            remove(name)
            if process:
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.terminate()
            BUDGET.release(name)


def cli_arguments(directory,tools,workspace_root="/workspace/output"):
    from .docker_runtime import runtime_arguments,mount
    descriptor=Path(directory)/'capabilities.json'
    state.atomic_json(descriptor,{'capability_policy':{'allowed':tools}})
    return runtime_arguments()+['--mount',mount(descriptor,'/job.json',True),'--env','RIGHAVEN_WORKSPACE_ROOT='+workspace_root]


class Service:
    def __init__(self,workspace,sid,user,thread,allowed):
        from .project_store import locked
        self.workspace,self.sid,self.user,self.thread=Path(workspace),sid,user,thread
        self.id=secrets.token_hex(16);self.cookie=secrets.token_urlsafe(32);self.token=secrets.token_urlsafe(32)
        self.container='rh-editor-'+self.id;self.state='preparing';self.message='Preparing editor software'
        self.csp_nonce=secrets.token_urlsafe(24)
        self.closed=False;self.error='';self.environment_id='';self.target='';self.resources=None;self.interface_version='';self.runtime_tools=[];self.runtime_versions={}
        self.cancel=threading.Event();self.last_seen=time.monotonic();self.started=self.last_seen;self.allowed=allowed
        self.proxy=f'/api/threads/{thread}/editors/{sid}/service/proxy/'
        with locked(workspace) as folder:
            self.directory,self.document=documents.record(folder,sid,allowed);self.before=documents.files(self.directory)
            SESSIONS[self.id]=self
        threading.Thread(target=self.run,daemon=True,name=self.container).start()

    def update(self,message):self.message=message

    def public(self):
        self.last_seen=time.monotonic()
        from urllib.parse import quote
        entry=documents.virtual_path(self.document).removeprefix('/mnt/user-data/') if self.document.get('mode')=='project' else self.document['entry']
        path='lab/tree/'+quote(entry,safe='/') if self.document['editor']=='jupyter' else 'vnc.html?autoconnect=true&resize=scale&path='+self.proxy.lstrip('/')+'websockify'
        return {'id':self.id,'state':self.state,'message':self.message,'editor':self.document['editor'],'environment_id':self.environment_id,'environment_profile':self.document.get('environment_profile'),'url':self.proxy+path,'error':self.error,'resources':self.resources,'interface_version':self.interface_version,'cli_version':self.document.get('cli_version',self.document['editor_version'])}

    def run(self):
        from .docker_runtime import docker,base_arguments,mount,remove,internal_daemon
        from .environment_runtime import release_claim,installation
        from .resource_budget import BUDGET
        try:
            definition=editor(self.document['editor'],self.allowed)
            from .editor_versions import software as select_software
            software=select_software(self.document,definition['tool'],self.container,self.cancel,user=self.user)
            self.runtime_tools=software.get('editor_allowed_tools') or software.get('tools') or [definition['tool']];self.runtime_versions={key:value for key,value in software.get('tool_version_names',{}).items() if key in self.runtime_tools}
            self.environment_id=software['id'];image=interface(software['image_id'],definition['package'],self.update,self.cancel,claim=self.container+'-interface')
            from .editor_profiles import remember
            remember(self.workspace,self.sid,self.allowed,self.user,software,image.split(':',1)[1])
            if self.cancel.is_set():return
            self.update('Waiting for interactive CPU/RAM; saved drafts are retained')
            self.resources=BUDGET.acquire(self.container,'editor',timeout=120,cancel=self.cancel)
            from .progress import workspace_key
            (self.directory/'home').mkdir(exist_ok=True,mode=0o700)
            args=base_arguments(self.container,self.resources)+['-d','--read-only','--tmpfs','/run:rw,size=16m','--user',f'{os.getuid()}:{os.getgid()}','-p','0.0.0.0::8080',
                '--label','org.righaven.harness.installation='+installation(),
                '--label','org.righaven.harness.workspace='+workspace_key(self.workspace),
                '--label','org.righaven.environment='+self.environment_id,'--label','org.righaven.editor='+definition['id'],
                '--mount',mount(documents.file_root(self.directory),'/workspace/output'),'--workdir','/workspace/output',
                '--mount',mount(self.directory/'home','/home/editor'),'--env','HOME=/home/editor','--env','DISPLAY=:99']
            # The selected public subtree is the writable project. The other public
            # chat folders are available too; control metadata and account files
            # are never mounted into an editor or notebook kernel.
            if self.document.get('mode')=='project':
                for public in ('uploads','outputs','workspace'):
                    public_path=documents.confined(self.workspace,self.workspace/public)
                    public_path.mkdir(parents=True,exist_ok=True)
                    args+=['--mount',mount(public_path,'/workspace/chat/'+public),'--mount',mount(public_path,'/mnt/user-data/'+public)]
            args+=cli_arguments(self.directory,self.runtime_tools,'/mnt/user-data' if self.document.get('mode')=='project' else '/workspace/output')
            if definition['package']=='notebook':
                (self.directory/'python').mkdir(exist_ok=True)
                args+=['--mount',mount(self.directory/'python','/workspace/python')]
                args+=[image,'/opt/righaven/jupyter-server/bin/python','/opt/righaven/editor_notebook.py','--allow-root','--no-browser','--ip=0.0.0.0','--port=8080',
                       '--IdentityProvider.token='+self.token,'--ServerApp.base_url='+self.proxy,
                       '--ServerApp.root_dir='+('/mnt/user-data' if self.document.get('mode')=='project' else '/workspace/output'),'--ServerApp.disable_check_xsrf=True',
                       '--ContentsManager.allow_hidden=True','--ServerApp.allow_remote_access=True','--ServerApp.terminals_enabled=True','--LabApp.expose_app_in_browser=True']
            else:
                args+=['--env','EDITOR_APP='+definition['id'],'--env','EDITOR_FILE='+(documents.virtual_path(self.document) if self.document.get('mode')=='project' else self.document['entry']),
                                          '--env','EDITOR_TOKEN='+self.token,image,'python3','/opt/righaven/editor_desktop.py']
            docker(*args,timeout=60)
            ports=json.loads(docker('inspect',self.container))[0]['NetworkSettings']['Ports']['8080/tcp'];port=int(ports[0]['HostPort'])
            # With the application daemon, this port is internal to runtime-docker,
            # never published on the outer VPS. No Docker socket enters the editor.
            self.target=f'http://runtime-docker:{port}' if internal_daemon() else f'http://127.0.0.1:{port}'
            import httpx
            self.update('Starting interactive application');deadline=time.monotonic()+90
            while not self.cancel.is_set():
                try:
                    with httpx.Client(timeout=3,trust_env=False) as client:
                        result=client.get(self.target+(self.proxy+'api/contents/'+__import__('urllib.parse',fromlist=['quote']).quote(documents.virtual_path(self.document).removeprefix('/mnt/user-data/') if self.document.get('mode')=='project' else self.document['entry'],safe='/') if definition['package']=='notebook' else '/vnc.html'),headers={'Authorization':'token '+self.token})
                        if result.status_code<400:break
                except httpx.HTTPError:pass
                if time.monotonic()>deadline:raise ValueError('Interactive application did not become ready')
                self.cancel.wait(.5)
            if definition['package']=='notebook':
                try:self.interface_version=docker('exec',self.container,'/opt/righaven/jupyter-server/bin/python','-c','import jupyterlab;print(jupyterlab.__version__)',timeout=10).strip()
                except Exception:self.interface_version=''
            self.state,self.message='ready','Editing project files directly' if self.document.get('mode')=='project' else 'Editing a private draft'
            while not self.cancel.wait(1):
                # Hidden browser tabs may throttle heartbeats to one per minute.
                if time.monotonic()-self.last_seen>180:break
                status=json.loads(docker('inspect',self.container))[0]['State']
                if not status['Running']:
                    if status.get('ExitCode')==0:break
                    raise ValueError('Interactive application stopped; draft files are retained')
        except Exception as error:self.error=str(error)[:1500];self.message=self.error
        finally:
            confirmed=False
            try:remove(self.container);confirmed=True
            except RuntimeError as error:self.error=str(error)
            release_claim(self.container)
            release_claim(self.container+'-interface')
            if confirmed:
                try:
                    from .project_store import locked
                    from .progress import utcnow
                    with locked(self.workspace) as folder:
                        root,value=documents.record(folder,self.sid,self.allowed);after=documents.files(root)
                        native=Path(value['entry']).with_suffix('.blend' if value['editor']=='blender' else '.FCStd') if value['editor'] in ('blender','freecad') else None
                        if native:
                            native_root,native_name=documents.file_location(root,native.as_posix())
                            if (native_root/native_name).is_file():value['entry']=str(native)
                        native_files=[row['name'] for row in after if Path(row['name']).suffix.lower() in editor(value['editor'],self.allowed)['native_extensions']]
                        if Path(value['entry']).suffix.lower() not in editor(value['editor'],self.allowed)['native_extensions'] and len(native_files)==1:value['entry']=native_files[0]
                        if after!=self.before:value.update(revision=value['revision']+1,updated_at=utcnow());state.atomic_json(root/'session.json',value)
                except (ValueError,OSError) as error:self.error=str(error)
            if confirmed:
                try:
                    from .environment_runtime import prune
                    prune()
                except (OSError,ValueError,subprocess.SubprocessError):pass
            self.closed=confirmed;self.state='failed' if self.error else 'stopped';self.message=self.error or ('Project files retained; reopen to continue editing' if self.document.get('mode')=='project' else 'Saved draft retained; reopen to continue editing')


def find(workspace,sid,user):
    with LOCK:return next((s for s in SESSIONS.values() if s.workspace==Path(workspace) and s.sid==sid and s.user==user and not s.closed),None)


def start(workspace,sid,user,thread,allowed):
    with LOCK:
        previous=find(workspace,sid,user)
        if previous:return previous
        from .runtime_settings import effective
        if effective().get('max_editors',2)==0:raise ValueError('Interactive editor sessions are disabled by the administrator')
        value=documents.get(workspace,sid,allowed)
        if editor(value['editor'],allowed)['mode'] not in ('service','desktop'):raise ValueError('This editor runs in the browser')
        return Service(workspace,sid,user,thread,allowed)


def stop_all():
    for service in list(SESSIONS.values()):service.cancel.set()
