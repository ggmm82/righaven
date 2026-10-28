"""Administrator-verified releases, immutable dependency plans and per-profile pins."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import uuid

from . import state
from .progress import utcnow,clean_summary

LOCK=threading.RLock()


def builtins():
    catalog=json.loads((state.ROOT/'versions.lock.json').read_text())
    result={a['id']:a for a in catalog['applications']}
    source=Path(os.getenv('RIGHAVEN_WORKER_SOURCE',Path(__file__).resolve().parents[1]))
    agy=json.loads((source/'scripts/antigravity.lock.json').read_text())
    result['provider-agy']={'id':'provider-agy','name':'Antigravity CLI','version':agy['version'],
        'repository':'https://github.com/google-antigravity/antigravity-cli','install':{'kind':'provider-agy'},
        'assets':{arch:{**asset,'name':asset['url'].rsplit('/',1)[1]} for arch,asset in agy['platforms'].items()}}
    result['provider-codex']={'id':'provider-codex','name':'Codex CLI','version':catalog['cli_runtimes']['codex'],
        'repository':'https://github.com/openai/codex','install':{'kind':'provider-codex'},'assets':{}}
    return result


def directory():
    root=state.STATE/'tool-versions';root.mkdir(parents=True,exist_ok=True)
    return root


def identifier(bundle):
    return hashlib.sha256(json.dumps(bundle,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def read(revision):
    if not re.fullmatch(r'[a-f0-9]{64}',revision):raise ValueError('Versione registrata non valida')
    path=directory()/(revision+'.json')
    if path.is_symlink() or path.stat().st_size>12*1024**2:raise ValueError('Pacchetto versione non valido')
    value=json.loads(path.read_text());validate(value['bundle'])
    if identifier(value['bundle'])!=revision:raise ValueError('Pacchetto versione modificato')
    return value


def validate(bundle):
    app=bundle.get('app') or {};tool=app.get('id');base=builtins().get(tool)
    if not base or not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.+:~_-]{0,100}',app.get('version','')):raise ValueError('Strumento o versione non riconosciuti')
    allowed={'version','assets','install'}
    if {k:v for k,v in app.items() if k not in allowed}!={k:v for k,v in base.items() if k not in allowed}:
        raise ValueError('Il pacchetto cambia il contratto dello strumento')
    install=app.get('install') or {};original=base.get('install') or {}
    if {k:v for k,v in install.items() if k!='source_dir'}!={k:v for k,v in original.items() if k!='source_dir'}:
        raise ValueError('La versione non può introdurre comandi di installazione')
    if 'source_dir' in install and (Path(install['source_dir']).is_absolute() or '..' in Path(install['source_dir']).parts):raise ValueError('Sorgente di build non valido')
    for asset in app.get('assets',{}).values():
        if not re.fullmatch(r'[a-f0-9]{64}',asset.get('sha256','')) or not str(asset.get('url','')).startswith('https://'):
            raise ValueError('Distribuzione non verificata')
    paths={'toolkit-lock/python/'+tool+'.txt','toolkit-lock/design/'+tool+'/package.json','toolkit-lock/design/'+tool+'/package-lock.json'}
    if tool=='playwright':paths={'toolkit-lock/package.json','toolkit-lock/package-lock.json'}
    if tool=='structurizr':paths={'toolkit-lock/design/structurizr/libraries.json'}
    if tool=='provider-codex':paths={'provider-clis/codex/package.json','provider-clis/codex/package-lock.json'}
    files=bundle.get('files',{})
    if not isinstance(files,dict) or set(files)-paths or sum(len(v.encode()) for v in files.values())>10*1024**2:
        raise ValueError('Dipendenze fuori dal contratto dello strumento')
    return bundle


def defaults():
    path=directory()/'defaults.json'
    return json.loads(path.read_text()) if path.exists() else {}


def activate(tool,revision):
    if tool not in builtins():raise ValueError('Strumento sconosciuto')
    if revision not in ('builtin','latest'):
        item=read(revision)
        if item['state']!='ready' or item['bundle']['app']['id']!=tool:raise ValueError('Verifica prima la versione selezionata')
    with LOCK:
        current=defaults();current[tool]=revision;state.atomic_json(directory()/'defaults.json',current)
    return {'tool':tool,'revision':revision}


def selections(user=None,profile=None,tools=None,engine=None):
    current=defaults();profile_pins={}
    if user and profile:
        from .environments import preferences
        profile_pins=preferences(user).get(profile,{}).get('tool_versions',{})
        current.update(profile_pins)
    from .environment_runtime import closure
    allowed=set(closure(tools or []))|{k for k in profile_pins if k.startswith('provider-')}
    provider={'codex':'provider-codex','gemini':'provider-agy'}.get(engine)
    if provider:allowed.add(provider)
    return {tool:revision for tool,revision in current.items() if tool in allowed and revision!='builtin'}


def packages(versions):return {tool:read(revision)['bundle'] for tool,revision in versions.items()}


def import_packages(versions,bundles):
    for tool,revision in versions.items():
        bundle=validate(bundles[tool])
        if bundle['app']['id']!=tool or identifier(bundle)!=revision:raise ValueError('Versione esportata modificata')
        state.atomic_json(directory()/(revision+'.json'),{'id':revision,'state':'ready','bundle':bundle,'imported':True,'updated_at':utcnow()})


def library():
    from .environment_runtime import closure
    rows=[]
    for path in sorted(directory().glob('*.json')):
        if not re.fullmatch(r'[a-f0-9]{64}',path.stem):continue
        try:
            row=read(path.stem);app=row['bundle']['app']
            rows.append({'id':row['id'],'tool':app['id'],'version':app['version'],'state':row['state'],'error':row.get('error',''),'updated_at':row['updated_at']})
        except (OSError,ValueError,KeyError):continue
    jobs=[]
    for path in sorted((directory()/'jobs').glob('*/status.json')):
        try:jobs.append(json.loads(path.read_text()))
        except (ValueError,OSError):continue
    return {'tools':[{'id':a['id'],'name':a['name'],'version':a['version'],'dependencies':[] if a['id'].startswith('provider-') else closure([a['id']])} for a in builtins().values()],
        'versions':rows,'jobs':sorted(jobs,key=lambda j:j.get('updated_at',''))[-20:],'defaults':defaults()}


def check_selection(value):
    if not isinstance(value,dict) or len(value)>50:raise ValueError('Selezione versioni non valida')
    for tool,revision in value.items():
        if tool not in builtins():raise ValueError('Strumento sconosciuto')
        if revision not in ('builtin','latest'):
            try:row=read(revision)
            except OSError as error:raise ValueError('Versione non presente: importa prima il pacchetto software o verifica nuovamente la release') from error
            if row['state']!='ready' or row['bundle']['app']['id']!=tool:raise ValueError('Versione non verificata')
    return value


def start(tool,version):
    from .release_catalog import VERSION
    if tool not in builtins() or not VERSION.fullmatch(version):raise ValueError('Strumento o versione non validi')
    with LOCK:
        for file in (directory()/'jobs').glob('*/status.json'):
            try:current=json.loads(file.read_text())
            except (OSError,ValueError):continue
            if current.get('tool')==tool and current.get('version')==version and current.get('state') in ('queued','resolving','testing'):
                return {'id':current['id'],'accepted':True,'existing':True}
        job_id=uuid.uuid4().hex;root=directory()/'jobs'/job_id;root.mkdir(parents=True)
        def status(phase,**fields):
            state.atomic_json(root/'status.json',{'id':job_id,'tool':tool,'version':version,'state':phase,'updated_at':utcnow(),**fields})
        status('queued')
    def work():
        from . import docker_runtime as runtime,environment_runtime as factory
        from .resource_budget import BUDGET
        from .release_catalog import candidate
        name='skill-version-'+job_id[:12];removed=False
        try:
            status('resolving')
            image=json.loads(runtime.docker('image','inspect',runtime.IMAGE))[0]
            arch={'amd64':'amd64','arm64':'arm64'}.get(image['Architecture'])
            if not arch:raise ValueError('Architettura non supportata')
            effective_version=latest_version(tool) if version=='latest' else version
            status('resolving',resolved_version=effective_version)
            spec=candidate(builtins()[tool],effective_version,arch)
            if spec.get('resolve_dependencies'):
                status('resolving',resolved_version=effective_version,operation_phase='queued')
                with runtime.BUILD_LOCK:
                    limits=BUDGET.acquire(name,'build',timeout=3600)
                    status('resolving',resolved_version=effective_version,operation_phase='resolving_dependencies')
                    request=root/'request.json';state.atomic_json(request,spec);request.chmod(0o644)
                    output=root/'output';output.mkdir(mode=0o777);output.chmod(0o777)
                    args=runtime.base_arguments(name,limits)+runtime.runtime_arguments(skills=True)
                    tmp=args.index('--tmpfs');del args[tmp:tmp+2]
                    for cap in ('CHOWN','FOWNER','DAC_OVERRIDE','SETUID','SETGID'):args+=['--cap-add',cap]
                    args+=['--label','org.righaven.harness.installation='+factory.installation(),
                        '--mount',runtime.mount(request,'/version-request.json',True),'--mount',runtime.mount(output,'/version-output'),
                        runtime.IMAGE,'python3','/opt/righaven/resolve_tool_version.py','/version-request.json','/version-output/resolved.json']
                    try:
                        result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=1800)
                    finally:
                        # Retain both admission and resources until reclamation is confirmed.
                        runtime.remove(name);removed=True
                    if result.returncode:raise ValueError('Risoluzione dipendenze non riuscita: '+clean_summary(result.stderr,1200))
                    source=output/'resolved.json'
                    if source.is_symlink() or source.stat().st_size>12*1024**2:raise ValueError('Piano dipendenze non valido')
                    bundle=json.loads(source.read_text())
            else:bundle={'app':spec['app'],'files':{}}
            validate(bundle);revision=identifier(bundle)
            existing=directory()/(revision+'.json')
            already_ready=existing.exists() and read(revision).get('state')=='ready'
            if not already_ready:state.atomic_json(existing,{'id':revision,'state':'testing','bundle':bundle,'updated_at':utcnow()})
            environment_id=factory.recipe([] if tool.startswith('provider-') else [tool],versions={tool:revision})[0]
            status('testing',revision=revision,environment_id=environment_id,resolved_version=bundle['app']['version'])
            tools=[] if tool.startswith('provider-') else [tool]
            verified=factory.ensure(tools,versions={tool:revision})
            state.atomic_json(directory()/(revision+'.json'),{'id':revision,'state':'ready','bundle':bundle,'environment_id':verified['id'],'updated_at':utcnow()})
            if version=='latest':
                with LOCK:
                    pointers=latest_pointers();pointers[tool]={'revision':revision,'version':bundle['app']['version'],'checked_at':time.time()}
                    state.atomic_json(directory()/'latest.json',pointers)
            status('ready',revision=revision,resolved_version=bundle['app']['version'])
        except Exception as error:
            failure={}
            if 'environment_id' in locals():failure=(factory.read(environment_id) or {}).get('failure') or {}
            status('failed',error=failure.get('message') or clean_summary(error,1600),failure=failure,environment_id=locals().get('environment_id',''))
            if 'revision' in locals() and not locals().get('already_ready',False) and read(revision).get('state')!='ready':
                state.atomic_json(directory()/(revision+'.json'),{'id':revision,'state':'failed','bundle':bundle,'error':clean_summary(error,1600),'updated_at':utcnow()})
        finally:
            if not removed:
                try:runtime.remove(name)
                except Exception:pass
            # remove() releases the lease only after confirmed cleanup.
    threading.Thread(target=work,daemon=True,name='tool-version').start()
    return {'id':job_id,'accepted':True}


def latest_pointers():
    path=directory()/'latest.json'
    return json.loads(path.read_text()) if path.exists() else {}


_LATEST={}
def latest_version(tool):
    from .release_catalog import latest
    cached=_LATEST.get(tool)
    if cached and time.monotonic()-cached[0]<600:return cached[1]
    value=latest(builtins()[tool]);_LATEST[tool]=(time.monotonic(),value)
    return value


def resolved(versions, *, wait=False, progress=None, cancel=None, on_progress=None, refresh=True):
    result={}
    for index,(tool,revision) in enumerate(versions.items(),1):
        def notify(phase,**fields):
            if on_progress:on_progress(phase=phase,tool=tool,index=index,total=len(versions),**fields)
        if wait:notify('resolving_versions',requested=revision,environment_id='',version='',version_job_id='',version_state='',version_operation='')
        if revision!='latest':result[tool]=revision;continue
        pointer=latest_pointers().get(tool,{})
        if wait and not refresh and pointer.get('revision'):
            cached=read(pointer['revision'])
            if cached.get('state')=='ready':
                result[tool]=pointer['revision'];continue
        if not wait:
            if pointer.get('revision'):result[tool]=pointer['revision']
            else:raise ValueError('Latest di '+tool+' da risolvere: prepara l’ambiente per verificarla')
            continue
        target=latest_version(tool)
        # Debian's signed stable repositories are resolved inside the matching base,
        # not against a different distribution on the Gateway.
        native_latest=target=='latest'
        if native_latest and pointer.get('revision') and time.time()-pointer.get('checked_at',0)<600:
            result[tool]=pointer['revision'];continue
        def matching():
            for row in library()['versions']:
                if row['tool']==tool and row['state']=='ready' and row['version'].lstrip('vn')==target.lstrip('vn'):return row['id']
        found=matching()
        if not found:
            jobs=[j for j in library()['jobs'] if j['tool']==tool and j['version'] in ('latest',target) and j['state'] in ('queued','resolving','testing')]
            job=jobs[0] if jobs else start(tool,'latest')
            deadline=time.monotonic()+3600
            while time.monotonic()<deadline:
                from .cancellation import requested
                from .progress import read_status
                if requested() or cancel is not None and cancel.is_set() or progress and any(read_status(progress).get(k) for k in ('cancel_requested','finish_requested')):
                    raise RuntimeError('Preparazione versione interrotta per questo incarico')
                status=json.loads((directory()/'jobs'/job['id']/'status.json').read_text())
                notify('checking_versions',version=status.get('resolved_version',target),version_job_id=job['id'],version_state=status['state'],version_operation=status.get('operation_phase',''),environment_id=status.get('environment_id',''))
                if status['state']=='failed':raise ValueError(status.get('error','Verifica versione non riuscita'))
                if status['state']=='ready':
                    found=status['revision'] if native_latest else matching()
                    if not found:raise ValueError('La release stabile è cambiata durante la verifica: ripeti la preparazione')
                    break
                time.sleep(.5)
            if not found:raise TimeoutError('Verifica della versione Latest non conclusa entro un’ora')
        result[tool]=found
        with LOCK:
            pointers=latest_pointers();pointers[tool]={'revision':found,'version':read(found)['bundle']['app']['version'],'checked_at':time.time()}
            state.atomic_json(directory()/'latest.json',pointers)
    return result


def recover_jobs():
    for path in (directory()/'jobs').glob('*/status.json'):
        try:
            value=json.loads(path.read_text())
            if value.get('state') in ('queued','resolving','testing'):
                value.update(state='failed',error='Verifica interrotta dal deploy; puoi ripeterla. Le versioni già pronte sono conservate.',updated_at=utcnow())
                state.atomic_json(path,value)
        except (OSError,ValueError):continue
