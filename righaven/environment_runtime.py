"""On-demand native runtime preparation, controlled only by the trusted Gateway."""
from contextlib import contextmanager, nullcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

from . import state
from .state import atomic_json, applications

RECIPE = 1
DEPS = {'mermaid':['playwright'],'excalidraw':['playwright'],'bpmn':['playwright'], 'axe-core':['playwright'],
        'aubio':['ffmpeg'],'whisper':['ffmpeg'],'manim':['ffmpeg'],'opentimelineio':['ffmpeg'],
        **{tool:['ffmpeg'] for tool in ('filmcraft','soundcraft','effectcraft','fluidsynth','musescore')}}
PREPARING = set()
STOPPING = threading.Event()
PREPARATION_CONTROL = {}
_PREPARING_LOCK = threading.Lock()
_CACHE_LOCK = threading.RLock()
_CLAIMS = {}


class PreparationDeferred(RuntimeError):pass
class PreparationCleanupError(RuntimeError):pass
class PreparationPublicationError(RuntimeError):pass


def check_cancel(cancel):
    if cancel and cancel.is_set():
        if getattr(cancel,'deferred',False):raise PreparationDeferred('Precaricamento in attesa della chat; le cache verificate sono conservate')
        raise RuntimeError('Preparazione annullata')


def interrupted(key,exc):
    deferred=isinstance(exc,PreparationDeferred)
    from .environment_preparation import diagnosis
    from .progress import clean_summary
    record=read(key) or {};previous=record.get('failure') or {}
    original=clean_summary(str(exc),6500)
    # _prepare and ensure both report the same exception. Preserve its original
    # phase on the outer report, but never reuse a prior attempt's diagnosis.
    if not deferred and original and record.get('status')=='failed' and previous.get('kind')=='publication' and previous.get('details','').startswith(original):return
    phase='publishing' if isinstance(exc,PreparationPublicationError) else record.get('status','')
    failure={} if deferred else diagnosis(preparation_text(key,since=record.get('attempt_started_at')),str(exc),phase=phase)
    save(key,status='waiting_chat' if deferred else 'failed',
         error='' if deferred else failure['message'],failure=failure,container='')


def stop_preparations():
    with _PREPARING_LOCK:
        STOPPING.set()
        for control in PREPARATION_CONTROL.values():
            control['reschedule']=False
            control['cancel'].set()


def enabled():
    return os.getenv('RIGHAVEN_ENVIRONMENT_MODE') == 'dynamic'


def closure(tools):
    known={a['id'] for a in applications()}
    if any(t not in known for t in tools):
        raise ValueError('Strumento non presente nel catalogo')
    result=set(tools); pending=list(tools)
    while pending:
        for dependency in DEPS.get(pending.pop(),[]):
            if dependency not in result:result.add(dependency);pending.append(dependency)
    return sorted(result)


def docker(*args, timeout=60):
    return subprocess.check_output(['docker',*args],text=True,timeout=timeout).strip()


def folder():
    path=state.STATE/'environments';path.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise ValueError('Cache ambienti non valida')
    return path


def installation():
    return (state.STATE/'installation-id').read_text().strip()


def recipe(tools, core=None, identity=None, versions=None):
    from .docker_runtime import IMAGE
    core=core or IMAGE
    selected=closure(tools)
    identity=identity or docker('image','inspect',core,'--format','{{.Id}}')
    spec={'version':RECIPE,'core':identity,'tools':selected}
    chosen={k:v for k,v in (versions or {}).items() if k in selected or k.startswith('provider-')}
    if chosen:spec['versions']=chosen
    key=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    return key,spec


def record_path(key):
    if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Identità ambiente non valida')
    return folder()/(key+'.json')


def image_tag(key):
    record_path(key)
    owner=hashlib.sha256(installation().encode()).hexdigest()[:12]
    return 'skill-environment:'+owner+'-'+key


def read(key):
    path=record_path(key)
    if not path.exists():return None
    if path.is_symlink() or path.stat().st_size>30000:raise ValueError('Stato ambiente non valido')
    return json.loads(path.read_text())


def save(key, **fields):
    value=read(key) or {'id':key,'created_at':time.time()}
    value.update(fields,updated_at=time.time());atomic_json(record_path(key),value)
    return value


def preparation_text(key, seen=None, *, since=None):
    seen=set() if seen is None else seen
    if key in seen or len(seen)>=8:return ''
    seen.add(key)
    value=read(key) or {}
    sections=[]
    dependencies=value.get('dependency_tools',[])
    if dependencies and value.get('core'):
        child,_=recipe(dependencies,identity=value['core'],versions=value.get('versions'))
        child_state=read(child) or {}
        title='Prerequisiti: '+', '.join(dependencies)
        if child_state.get('status')=='ready':sections.append(title+' — già verificati e disponibili')
        else:sections.append(title+'\n'+preparation_text(child,seen,since=since))
    path=folder()/(key+'.log')
    if path.exists() and not path.is_symlink() and (since is None or path.stat().st_mtime>=since):
        with path.open('rb') as stream:
            stream.seek(max(0,path.stat().st_size-12000))
            sections.append(stream.read(12000).decode('utf-8',errors='replace'))
    return '\n\n'.join(sections)[-20000:]


def preparation_observation(key, *, since=None):
    """Observe software preparation, including shared prerequisites and queue waits.

    No project/user names or invented heartbeat: output timestamps come from logs.
    """
    now=time.time();seen=set()
    def observe(identifier):
        if not identifier or identifier in seen or len(seen)>=8:return None
        seen.add(identifier);value=read(identifier) or {}
        if not value:return None
        tools=value.get('tools',[]);phase=value.get('status','queued')
        dependencies=value.get('dependency_tools',[])
        if dependencies and value.get('core'):
            child,_=recipe(dependencies,identity=value['core'],versions=value.get('versions'))
            child_value=read(child) or {}
            if child_value.get('status')!='ready':
                result=observe(child)
                if result:return {**result,'prerequisite':True}
        path=folder()/(identifier+'.log');last_output=None;size=0;recent=''
        if path.is_file() and not path.is_symlink():
            stat=path.stat()
            if since is None or stat.st_mtime>=since:
                last_output=stat.st_mtime;size=stat.st_size
                with path.open('rb') as stream:
                    stream.seek(max(0,size-4096));tail=stream.read(4096).decode('utf-8',errors='replace')
                from .progress import clean_summary
                recent=next((clean_summary(line,300) for line in reversed(tail.splitlines()) if line.strip()),'')
        return {'environment_id':identifier,'phase':phase,'tools':tools,'last_output_at':last_output,
            'log_bytes':size,'recent_output':recent,'observed_at':now,'prerequisite':False}
    result=observe(key) or {'environment_id':key or '', 'phase':'queued','tools':[],
        'last_output_at':None,'log_bytes':0,'recent_output':'','observed_at':now,'prerequisite':False}
    if result['phase'] in ('queued','waiting_chat'):
        # Only an actual preparation with a container is reported as occupying
        # the shared slot. A queued request or stale parent is not work progress.
        occupying=[]
        for path in sorted(folder().glob('*.json')):
            try:value=read(path.stem) or {}
            except (OSError,ValueError):continue
            if value.get('container') and value.get('status') in ('installing','adapters','checking','publishing'):
                occupying.append(value)
        if occupying:result['waiting_on']={'tools':sorted({tool for value in occupying for tool in value.get('tools',[])}),'phase':'preparing','count':len(occupying)}
    return result


def image_exists(value, cache=None):
    if not value or value.get('status')!='ready':return False
    try:
        if cache is not None and value['image'] in cache:return cache[value['image']]
        data=json.loads(docker('image','inspect',value['image']))[0]
        labels=data.get('Config',{}).get('Labels') or {}
        valid=(data['Id']==value.get('image_id') and labels.get('org.righaven.environment')==value['id']
                and labels.get('org.righaven.harness.installation')==installation())
        if cache is not None:cache[value['image']]=valid
        return valid
    except (ValueError,KeyError,subprocess.SubprocessError):return False


def matching_versions(value,spec,subset=False,reset_providers=False):
    have=value.get('versions',{});wanted=spec.get('versions',{})
    tools=value.get('tools',[]) if subset else spec['tools']
    if any(have.get(t)!=wanted.get(t) for t in tools):return False
    if subset and not reset_providers and any(k.startswith('provider-') and k not in wanted for k in have):return False
    if not subset:
        providers={k for k in set(have)|set(wanted) if k.startswith('provider-')}
        if any(have.get(t)!=wanted.get(t) for t in providers):return False
    return True


def candidates(spec, cache=None):
    result=[]
    for path in folder().glob('*.json'):
        try:
            item=read(path.stem)
            if item.get('core')==spec['core'] and set(spec['tools']).issubset(item.get('tools',[])) and matching_versions(item,spec) and image_exists(item, cache):result.append(item)
        except (OSError,ValueError):continue
    return sorted(result,key=lambda x:len(x['tools']))


def subset(spec):
    ready=[]
    for path in folder().glob('*.json'):
        try:
            value=read(path.stem)
            if (value.get('core')==spec['core'] and set(value.get('tools',[]))<=set(spec['tools'])
                    and matching_versions(value,spec,True,reset_providers=True) and (set(value.get('tools',[]))<set(spec['tools']) or value.get('versions',{})!=spec.get('versions',{}))
                    and image_exists(value)):ready.append(value)
        except (ValueError,OSError):continue
    return max(ready,key=lambda v:v.get('size_bytes',0),default=None)


def available(tools, identity=None, cache=None, versions=None):
    key,spec=recipe(tools,identity=identity,versions=versions)
    if not spec['tools'] and not spec.get('versions'):return {'id':key,'status':'ready','tools':[],'core':True}
    exact=read(key)
    if exact and exact.get('status') in ('queued','installing','adapters','checking','publishing'):
        return exact
    ready=candidates(spec,cache)
    if ready:return ready[0]
    if exact and exact.get('status')!='ready':return exact
    return {'id':key,'status':'on_demand','tools':spec['tools']}


def claim_environment(record, owner):
    # Pin a selected image before docker run creates its container reference.
    # Otherwise a concurrent preload's cache pruning could remove it in between.
    if owner:
        with _CACHE_LOCK: _CLAIMS[owner] = record['id']
    return record


def release_claim(owner):
    with _CACHE_LOCK: _CLAIMS.pop(owner, None)


@contextmanager
def preparation_slot(slot, acquire, cancel, progress, *, background=False):
    if not acquire:
        yield
        return
    while True:
        check_cancel(cancel)
        if progress:
            from .progress import read_status
            from .cancellation import requested
            if requested() or read_status(progress).get('cancel_requested') or read_status(progress).get('finish_requested'):
                raise RuntimeError('Preparazione annullata prima dell’avvio')
        if background:
            if not slot.acquire_background(cancel,cancel.yield_event):check_cancel(cancel)
            else:break
        elif slot.acquire(timeout=.25):break
    try:yield
    finally:slot.release()


_RECIPE_LOCKS={}
_BUILD_PINS={}


@contextmanager
def recipe_slot(key,cancel):
    # Deduplicate one image without serializing unrelated recipes. Waiting never
    # owns a preparation slot or a resource lease.
    with _CACHE_LOCK:
        entry=_RECIPE_LOCKS.setdefault(key,{'lock':threading.Lock(),'users':0});entry['users']+=1
    acquired=False
    try:
        while not acquired:
            check_cancel(cancel);acquired=entry['lock'].acquire(timeout=.25)
        yield
    finally:
        if acquired:entry['lock'].release()
        with _CACHE_LOCK:
            entry['users']-=1
            if not entry['users']:_RECIPE_LOCKS.pop(key,None)


def ensure(tools, *, acquire=True, progress=None, exact=False, cancel=None, cache_dependencies=True, deadline=None, claim=None, versions=None, background=False):
    from .tool_versions import resolved
    versions=resolved(versions or {},wait=True,progress=progress,refresh=False)
    key,spec=recipe(tools,versions=versions)
    with recipe_slot(key,cancel):
        try:
            return _prepare(key,spec,acquire=acquire,progress=progress,exact=exact,cancel=cancel,
                cache_dependencies=cache_dependencies,deadline=deadline,claim=claim,versions=versions,background=background)
        finally:
            with _CACHE_LOCK:_BUILD_PINS.pop(key,None)


def _prepare(key,spec, *, acquire,progress,exact,cancel,cache_dependencies,deadline,claim,versions,background):
    """Prepare only locked binaries. No credentials, project mount, socket or generated code."""
    from .docker_runtime import IMAGE, BUILD_LOCK, base_arguments, host_path, remove, LABEL, OWNER, runtime_arguments
    from .tool_versions import packages,builtins
    check_cancel(cancel)
    if not spec['tools'] and not spec.get('versions'):return {'id':key,'image':IMAGE,'tools':[],'status':'ready','core':True}
    with _CACHE_LOCK:
        ready=read(key)
        if image_exists(ready):
            return claim_environment(save(key,last_used=time.time(),error='',failure={}),claim)
        if not exact:
            ready=candidates(spec)
            if ready:
                return claim_environment(save(ready[0]['id'],last_used=time.time(),error='',failure={}),claim)
        save(key,status='queued',tools=spec['tools'],core=spec['core'],versions=spec.get('versions',{}),error='',failure={},container='',attempt_started_at=time.time())
    deadline=deadline if deadline is not None else time.monotonic()+3600
    try:
        check_cancel(cancel)
        if time.monotonic()>deadline:raise TimeoutError('Tempo di preparazione ambiente esaurito')
        # Finish shared prerequisites before admission: never hold a parent build
        # slot while another request needs that slot to finish our dependency.
        dependencies=sorted({d for tool in spec['tools'] for d in DEPS.get(tool,[])})
        if cache_dependencies and dependencies and set(dependencies)<set(spec['tools']):
            save(key,status='installing',tools=spec['tools'],core=spec['core'],dependency_tools=dependencies)
            dependency_key,_=recipe(dependencies,identity=spec['core'],versions=versions)
            with _CACHE_LOCK:_BUILD_PINS.setdefault(key,set()).add(dependency_key)
            ensure(dependencies,acquire=acquire,progress=progress,exact=True,cancel=cancel,
                deadline=deadline,versions=versions,background=background)
    except Exception as exc:
        interrupted(key,exc)
        raise
    save(key,status='queued',container='')
    with preparation_slot(BUILD_LOCK, acquire, cancel, progress,background=background):
        ready=read(key)
        if image_exists(ready):return claim_environment(save(key,last_used=time.time(),error='',failure={}),claim)
        if not exact:
            ready=candidates(spec)
            if ready:
                save(ready[0]['id'],last_used=time.time(),error='',failure={})
                return claim_environment(ready[0],claim)
        with _CACHE_LOCK:
            base=subset(spec)
            if base:_BUILD_PINS.setdefault(key,set()).add(base['id'])
        protected=(key,base['id']) if base else (key,)
        prune(exclude=protected)
        base_image=base['image_id'] if base else spec['core']
        from .runtime_settings import effective
        limits=effective()
        name='rh-env-'+key[:12]+'-'+uuid.uuid4().hex[:6]
        descriptor=folder()/(name+'.request.json')
        resets={tool:builtins()[tool] for tool in (base or {}).get('versions',{})
                if tool.startswith('provider-') and tool not in spec.get('versions',{})}
        atomic_json(descriptor,{'tools':spec['tools'],'versions':spec.get('versions',{}),'version_packages':packages(spec.get('versions',{})),
                                'reset_providers':resets})
        # Only public catalog IDs: readable under dropped capabilities/user namespaces too.
        descriptor.chmod(0o644)
        image=image_tag(key)
        log=folder()/(key+'.log')
        error='Preparazione non completata'
        cleaned=False
        try:
            check_cancel(cancel)
            from .resource_budget import BUDGET
            class BudgetCancel:
                def is_set(self):
                    check_cancel(cancel)
                    return False
            limits = BUDGET.acquire(name, 'build', cancel=BudgetCancel(), timeout=max(0, deadline-time.monotonic()))
            if progress:BUDGET.observe_progress(name,progress)
            save(key,status='installing',error='',tools=spec['tools'],core=spec['core'],container=name,versions=spec.get('versions',{}))
            if progress:
                from .progress import update
                update(progress, environment_container=name)
            # /tmp is not a tmpfs: native compiler/npm downloads need bounded disk, not the worker RAM budget.
            args=base_arguments(name,limits) + runtime_arguments(skills=True)
            tmp=args.index('--tmpfs');del args[tmp:tmp+2]
            # Curated package maintainers need ownership and apt's _apt user transitions.
            # These capabilities belong only to preparation, never to AI workers.
            for capability in ('CHOWN','FOWNER','DAC_OVERRIDE','SETUID','SETGID'):
                args += ['--cap-add',capability]
            if progress:
                from .progress import read_status
                args += ['--label','org.righaven.harness.workspace='+read_status(progress)['workspace_key']]
            args += ['--label','org.righaven.harness.installation='+installation(),
                '--label','org.righaven.environment='+key,
                '--mount','type=bind,src='+host_path(descriptor)+',dst=/environment-request.json,readonly',
                base_image,'python3','/opt/righaven/prepare_environment.py','/environment-request.json']
            process=subprocess.Popen(['docker',*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
            pending=''
            with log.open('w') as output:
                while process.poll() is None:
                    check_cancel(cancel)
                    if progress:
                        from .cancellation import requested
                        from .progress import update
                        if requested() or any(__import__('harness.progress',fromlist=['read_status']).read_status(progress).get(k) for k in ('cancel_requested','finish_requested')):
                            raise RuntimeError('Preparazione annullata; i file del progetto sono conservati')
                        update(progress,heartbeat_at=__import__('harness.progress',fromlist=['utcnow']).utcnow())
                    if time.monotonic()>deadline:raise TimeoutError('Tempo di preparazione ambiente esaurito')
                    # select keeps cancellation and heartbeat responsive during quiet compiler commands.
                    import select
                    if select.select([process.stdout],[],[],1)[0]:
                        chunk=os.read(process.stdout.fileno(),65536).decode('utf-8',errors='replace')
                        if output.tell()<2_000_000:output.write(chunk);output.flush()
                        pending=(pending+chunk)[-100000:]
                        while '\n' in pending:
                            line,pending=pending.split('\n',1)
                            try:
                                event=json.loads(line)
                                if event.get('phase') in ('installing','adapters','checking','publishing'):
                                    save(key,status=event['phase'])
                            except (ValueError,AttributeError):pass
                tail=process.stdout.read().decode('utf-8',errors='replace')
                if output.tell()<2_000_000:output.write(tail[:100000])
            if process.returncode:
                raw=docker('inspect','--format','{{json .State}}',name)
                if json.loads(raw).get('OOMKilled'):error='Memoria insufficiente durante la preparazione'
                else:error='Preparazione o verifica nativa non riuscita; consulta i dettagli dell’ambiente'
                raise RuntimeError(error)
            check_cancel(cancel)
            save(key,status='publishing')
            with log.open('a') as output:
                output.write('\n'+json.dumps({'phase':'publishing','at':time.time(),'message':'Collaudi superati; salvataggio dell’immagine software Docker'})+'\n')
            identifier=docker('commit','--change','LABEL org.righaven.environment='+key,
                '--change','LABEL org.righaven.harness.installation='+installation(),
                '--change','CMD ["python3","-c","print(\\"Ambiente RigHaven pronto\\")"]',name,image,timeout=900)
            inspected=json.loads(docker('image','inspect',identifier))[0]
            remove(name)
            cleaned=True
            result=save(key,status='ready',image=image,image_id=inspected['Id'],size_bytes=inspected['Size'],
                last_used=time.time(),container='',tools=spec['tools'],core=spec['core'],error='',failure={},
                base_image_id=base_image,reused_tools=base['tools'] if base else [],versions=spec.get('versions',{}),version_names={k:v['app']['version'] for k,v in packages(spec.get('versions',{})).items()})
            prune(exclude=(key,))
            return claim_environment(result,claim)
        except Exception as exc:
            if (read(key) or {}).get('status')=='publishing' and not isinstance(exc,PreparationPublicationError):
                failure=PreparationPublicationError(str(exc))
                interrupted(key,failure)
                raise failure from exc
            interrupted(key,exc)
            raise
        finally:
            try:
                if not cleaned:
                    try:
                        remove(name)
                        cleaned=True
                    except Exception as exc:
                        message='Pulizia del precaricamento non confermata; riavvia il Gateway per recuperare le risorse'
                        from .resource_budget import BUDGET
                        BUDGET.quarantine(message)
                        BUILD_LOCK.quarantine(message)
                        save(key,status='failed',error=message)
                        raise PreparationCleanupError(message) from exc
            finally:
                try:
                    if 'process' in locals():
                        if process.poll() is None:process.kill()
                        process.wait(timeout=10)
                        process.stdout.close()
                finally:
                    if cleaned:
                        from .resource_budget import BUDGET
                        BUDGET.release(name)
                    descriptor.unlink(missing_ok=True)


def source_tools(workspace, task, selected):
    """Reopening a colleague's native sources needs their actual engine too."""
    import re,zipfile
    from .projects import artifact_path
    from .source_packages import DESIGN_NATIVE,PRODUCTION_NATIVE
    mapping={**DESIGN_NATIVE,**{k:v[0] for k,v in PRODUCTION_NATIVE.items()},
        '.blend':'blender','.fcstd':'freecad','.fcproj':'filmcraft','.ecproj':'effectcraft','.scraft':'soundcraft',
        '.epub':'calibre','.azw3':'calibre'}
    mapping.pop('.py',None)  # A generic Python script does not imply Manim.
    result=set(selected)
    for text in re.findall(r'/mnt/user-data/[^\s\"\'`<>]+',task)[:160]:
        path=artifact_path(workspace,text.rstrip('.,;:)'))
        if not path:continue
        if path.suffix.lower() in mapping:result.add(mapping[path.suffix.lower()])
        if path.suffix.lower()=='.zip' and path.stat().st_size<=512*1024**2:
            try:
                with zipfile.ZipFile(path) as archive:
                    if len(archive.infolist())>12000:continue
                    for item in archive.infolist():
                        tool=mapping.get(Path(item.filename).suffix.lower())
                        if tool:result.add(tool)
            except (OSError,zipfile.BadZipFile):pass
    return sorted(result)


def pinned():
    """Derive pins from native Agent scopes and deployment preferences, never a second skill list."""
    from righaven_core.config.paths import get_paths
    from .environments import preferences, preloaded_tools
    from .capability_policy import native_policy
    users=get_paths().base_dir/'users'
    from .environment_transfers import active_images
    result=active_images()
    with _CACHE_LOCK:
        result.update(_CLAIMS.values());result.update(_RECIPE_LOCKS)
        for values in _BUILD_PINS.values():result.update(values)
    if users.exists():
        for user in users.iterdir():
            if not user.is_dir() or user.is_symlink():continue
            try:preferences_for_user=preferences(user.name)
            except (ValueError,OSError):continue
            for name,prefs in preferences_for_user.items():
                if prefs.get('mode')=='preload':
                    # Protect the software actually prepared, even when an
                    # explicitly checked Latest pointer has since advanced.
                    from .environment_preparation import read as preparation_record
                    retained=preparation_record(user.name,name).get('ready_id')
                    if retained:result.add(retained)
                    try:
                        policy=native_policy(user.name,name)
                        from .tool_versions import selections,resolved
                        from .state import team
                        tools=preloaded_tools(prefs,policy['allowed'])
                        pins=resolved(selections(user.name,name,tools,team('squad')['engine']))
                        key,_=recipe(tools,versions=pins);result.add(key)
                    except (ValueError,OSError):continue
    return result


def evict(key):
    with _CACHE_LOCK:
        return _evict(key)


def _evict(key):
    value=read(key)
    if not value or not image_exists(value):return {'removed':False}
    if key in _CLAIMS.values():raise ValueError('Ambiente assegnato a un incarico; attendi il rilascio')
    if key in pinned():raise ValueError('Ambiente mantenuto pronto da un profilo con predeploy')
    if docker('ps','-aq','--filter','ancestor='+value['image_id']):
        raise ValueError('Ambiente in uso: attendi la chiusura dei lavori')
    docker('image','rm','--no-prune',value['image'],timeout=120)
    save(key,status='on_demand',image='',image_id='',size_bytes=0)
    return {'removed':True}


def cache_settings():
    path=state.STATE/'environment-cache.json'
    if path.is_symlink():raise ValueError('Budget cache non valido')
    return json.loads(path.read_text()) if path.exists() else {'max_gib':20,'max_idle_days':14}


def prune(exclude=()):
    settings=cache_settings(); rows=[]
    for path in folder().glob('*.json'):
        try:
            value=read(path.stem)
            if value and value.get('status')=='ready':rows.append(value)
        except ValueError:continue
    total=sum(v.get('size_bytes',0) for v in rows)
    now=time.time();pins=pinned()
    for row in sorted(rows,key=lambda r:r.get('last_used',r['created_at'])):
        if row['id'] in exclude or row['id'] in pins:continue
        expired=now-row.get('last_used',row['created_at'])>settings['max_idle_days']*86400
        if not expired and total<=settings['max_gib']*1024**3:continue
        try:
            if evict(row['id']).get('removed'):total-=row.get('size_bytes',0)
        except (ValueError,OSError,subprocess.SubprocessError):continue


def reconcile():
    for path in folder().glob('*.json'):
        try:
            value=read(path.stem)
            if value.get('status') in ('queued','installing','adapters','checking','publishing','waiting_chat'):
                error='Preparazione interrotta dal riavvio. Puoi ripeterla senza perdere i progetti.'
                if value.get('status')=='publishing':interrupted(path.stem,PreparationPublicationError(error))
                else:save(path.stem,status='failed',container='',error=error)
        except ValueError:continue
