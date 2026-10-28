"""Portable, administrator-supplied software images; never account or project state."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import uuid

from . import environment_runtime as factory, runtime_bundle as bundle
from .state import atomic_json

FORMAT = 'skill-software-environment'
MAX_BYTES = 16 * 1024**3


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024**2), b''):digest.update(chunk)
    return digest.hexdigest()


def capacity(path, required):
    if shutil.disk_usage(path).free < required + 512*1024**2:
        raise ValueError('Spazio insufficiente per il trasferimento dell’ambiente')


def rebuild_files(directory, tools, versions=None):
    """Self-contained build context, with read-only BuildKit adapter mounts."""
    root = Path(os.getenv('RIGHAVEN_WORKER_SOURCE', Path(__file__).resolve().parents[1]))
    destination = Path(directory); destination.mkdir()
    dockerfile = (root/'docker/Dockerfile.sandbox').read_text().split('FROM software AS core')[0]
    # All and only the stable stage COPY inputs; no arbitrary Gateway or state files.
    import shlex
    for line in dockerfile.splitlines():
        if not line.startswith('COPY '):continue
        for relative in shlex.split(line)[1:-1]:
            source=root/relative;target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if source.is_dir():shutil.copytree(source,target)
            else:shutil.copy2(source,target)
    mounts=[]
    for section,name,source in bundle.sources():
        target=destination/'bundle'/section/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);target.chmod(0o755 if name.endswith('.py') else 0o644)
        if section=='righaven':mounts.append('--mount=type=bind,source=bundle/righaven/'+name+',target=/opt/righaven/'+name)
    skills=Path(os.getenv('RIGHAVEN_BUNDLED_SKILLS',Path(__file__).resolve().parents[1]/'skills'))
    shutil.copytree(skills,destination/'bundle/skills')
    from .tool_versions import packages
    versions=versions or {}
    (destination/'request.json').write_text(json.dumps({'tools':tools,'versions':versions,'version_packages':packages(versions)}))
    mounts.extend(['--mount=type=bind,source=bundle/righaven-worker,target=/opt/righaven-worker',
                   '--mount=type=bind,source=bundle/skills,target=/mnt/skills'])
    (destination/'Dockerfile.software').write_text(dockerfile)
    from .docker_runtime import IMAGE
    dockerfile='# syntax=docker/dockerfile:1\nARG SOFTWARE_IMAGE='+IMAGE+'\nFROM ${SOFTWARE_IMAGE} AS software\n'
    dockerfile+='\nCOPY request.json /environment-request.json\nRUN '+ ' \\\n    '.join(mounts)+' \\\n    python3 /opt/righaven/prepare_environment.py /environment-request.json\n'
    (destination/'Dockerfile').write_text(dockerfile)
    shutil.copy2(root/'scripts/package_environment_image.py',destination/'package.py')
    shutil.copy2(root/'righaven/docker_archives.py',destination/'docker_image_archive.py')
    (destination/'README.txt').write_text('Ricostruzione dei programmi: docker build -t skill-environment-rebuilt .\nBase completa da zero: docker build -f Dockerfile.software -t skill-software-rebuilt .\nPer usarla: docker build --build-arg SOFTWARE_IMAGE=skill-software-rebuilt -t skill-environment-rebuilt .\n'
        'BuildKit richiesto. Download verificati con i lock inclusi. Sistema operativo e repository apt possono evolvere: '
        'la ricostruzione non garantisce lo stesso digest. Per il trasferimento identico usare image.tar.\n'
        'Dopo la build: python3 package.py skill-environment-rebuilt --output ../rebuilt.righaven-env.tar\n'
        'Per una base ricostruita aggiungere --base skill-software-rebuilt; la destinazione deve usare la stessa base.\n'
        'Questo contesto non contiene account, progetti o skill personali. Importare il pacchetto software nel profilo desiderato; '
        'la configurazione Agent si esporta separatamente dalla pagina Ambienti.\n')
    (destination/'recipe-files.json').write_text(json.dumps({'files':sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()),
        'tools':tools,'versions':versions,'software_image':IMAGE,'recipe':factory.RECIPE}))


def export_image(value, directory,on_progress=None):
    if on_progress:on_progress('waiting_image','Attendo l’accesso all’immagine da esportare')
    with factory.recipe_slot(value['id'],None):
        current=factory.read(value['id']) or value
        return _export_image(current,directory,on_progress)


def _export_image(value,directory,on_progress=None):
    if value.get('core') is True or not (value.get('tools') or value.get('versions')) or not factory.image_exists(value):
        raise ValueError('Prepara un ambiente con programmi prima di esportarlo')
    root=Path(directory);capacity(root,max(value.get('size_bytes',0)*3,512*1024**2))
    details=json.loads(factory.docker('image','inspect',value['image_id']))[0]
    image=root/'image.tar'
    from .docker_archives import save_image
    info=save_image(value['image'],details,image,on_progress=on_progress)
    if image.stat().st_size>MAX_BYTES:raise ValueError('Ambiente oltre il limite di trasferimento di 16 GiB')
    manifest={'format':FORMAT,'version':1,'software_id':value['core'],'recipe':factory.RECIPE,
              'tools':value['tools'],'versions':value.get('versions',{}),'image_id':info['config_digest'],'image_config_digest':info['config_digest'],
              'source_image_id':details['Id'],'software_layers':json.loads(factory.docker('image','inspect',value['core']))[0]['RootFS']['Layers'],
              'layer_count':len(info['layers']),'image_bytes':image.stat().st_size,'os':details['Os'],
              'architecture':details['Architecture'],'variant':details.get('Variant',''),
              'image_sha256':checksum(image)}
    if on_progress:on_progress('packaging','Preparazione del pacchetto completo con immagine, Dockerfile e ricetta')
    atomic_json(root/'manifest.json',manifest)
    rebuild_files(root/'rebuild',value['tools'],value.get('versions'))
    archive=root/'environment.righaven-env.tar'
    def portable_header(info):
        info.uid=info.gid=0;info.uname=info.gname='root'
        info.mode=0o755 if info.isdir() or info.mode&0o111 else 0o644
        return info
    with tarfile.open(archive,'w') as target:
        for name in ('manifest.json','image.tar','rebuild'):target.add(root/name,arcname=name,filter=portable_header)
    image.unlink();shutil.rmtree(root/'rebuild');(root/'manifest.json').unlink()
    return archive


def unpack(path, directory):
    root=Path(directory)
    with tarfile.open(path,'r:') as archive:
        members=[]
        for member in archive:
            members.append(member)
            if len(members)>10000:raise ValueError('Troppi file nel pacchetto')
        if len(members)>10000 or sum(m.size for m in members)>MAX_BYTES+32*1024**2:raise ValueError('Pacchetto troppo grande')
        names=set()
        for item in members:
            name=Path(item.name)
            if (item.name in names or name.is_absolute() or '..' in name.parts or '\\' in item.name
                    or not (item.isfile() or item.isdir())):raise ValueError('Pacchetto ambiente non valido')
            names.add(item.name)
        metadata=archive.getmember('manifest.json')
        if not metadata.isfile() or metadata.size>64000:raise ValueError('Manifest non valido')
        manifest=json.load(archive.extractfile(metadata))
        if not isinstance(manifest,dict) or manifest.get('format')!=FORMAT or manifest.get('version')!=1:
            raise ValueError('Formato ambiente non supportato')
        if manifest.get('versions'):
            request=archive.getmember('rebuild/request.json')
            if not request.isfile() or request.size>12*1024**2:raise ValueError('Ricetta versioni non valida')
            recipe=json.load(archive.extractfile(request))
            if recipe.get('versions')!=manifest['versions']:raise ValueError('Versioni diverse dalla ricetta')
            bundles=recipe.get('version_packages',{})
            from .tool_versions import validate,identifier
            if set(bundles)!=set(manifest['versions']):raise ValueError('Piani delle dipendenze mancanti')
            for tool,revision in manifest['versions'].items():
                plan=validate(bundles[tool])
                if plan['app']['id']!=tool or identifier(plan)!=revision:raise ValueError('Piano versione modificato')
            manifest['_version_packages']=bundles
        image=archive.getmember('image.tar')
        if not image.isfile() or image.size>MAX_BYTES:raise ValueError('Immagine non valida')
        capacity(root,image.size*3)
        destination=root/'image.tar'
        with archive.extractfile(image) as source,destination.open('wb') as output:shutil.copyfileobj(source,output,1024**2)
    if checksum(destination)!=manifest.get('image_sha256'):raise ValueError('Checksum immagine non valido')
    from .docker_archives import validate,normalize
    info=validate(destination,expected_config=manifest.get('image_config_digest') or manifest.get('image_id'))
    with tarfile.open(destination,'r:') as archive:oci=any(member.name=='index.json' for member in archive)
    if oci:
        normalized=root/'image-normalized.tar'
        normalize(destination,normalized)
        destination.unlink();normalized.rename(destination)
    manifest['image_layers']=info['diff_ids']
    return manifest,destination


def import_image(path, directory, expected_tools, allowed_tools=None,on_progress=None):
    from .docker_runtime import IMAGE, base_arguments, host_path, remove, runtime_arguments
    if on_progress:on_progress('checking_package','Verifica del pacchetto, dei checksum e della compatibilità')
    metadata,image=unpack(path,directory)
    tools=metadata.get('tools')
    if not isinstance(tools,list) or not (tools or metadata.get('versions')) or len(tools)>64 or any(not isinstance(t,str) for t in tools) or factory.closure(tools)!=tools or not set(expected_tools).issubset(tools):
        raise ValueError('Programmi del pacchetto incompatibili con il profilo selezionato')
    if allowed_tools is not None:
        excluded=set(tools)-set(factory.closure(allowed_tools))
        if excluded:raise ValueError('Il pacchetto include programmi esclusi dal profilo: '+', '.join(sorted(excluded))+'. Seleziona un profilo compatibile prima di importarlo.')
    versions=metadata.get('versions',{})
    key,spec=factory.recipe(tools,versions=versions)
    base=json.loads(factory.docker('image','inspect',IMAGE))[0]
    compatible=metadata.get('software_layers')==base['RootFS']['Layers'] if metadata.get('software_layers') else metadata.get('software_id')==spec['core']
    if metadata.get('recipe')!=factory.RECIPE or not compatible:
        raise ValueError('Base software diversa: usare lo stesso rilascio dei programmi o ricostruire con il Dockerfile allegato')
    for field,source in (('os','Os'),('architecture','Architecture'),('variant','Variant')):
        if metadata.get(field,'')!=base.get(source,''):raise ValueError('Architettura o sistema operativo non compatibili')
    from .docker_runtime import BUILD_LOCK
    if on_progress:on_progress('waiting_resources','Attendo le risorse per verificare l’ambiente importato')
    with factory.recipe_slot(key,None),factory.preparation_slot(BUILD_LOCK,True,None,None):
        return _import_image(metadata,image,directory,tools,versions,key,spec,base,on_progress)


def _import_image(metadata,image,directory,tools,versions,key,spec,base,on_progress=None):
    from .docker_runtime import base_arguments,host_path,remove,runtime_arguments
    from .docker_archives import load_image,forget_tag
    if on_progress:on_progress('loading_image','Caricamento dell’immagine nel Docker del server')
    import_tag,loaded=load_image(image,directory)
    try:
        if loaded['RootFS']['Layers']!=metadata['image_layers'] or loaded['RootFS']['Layers'][:len(base['RootFS']['Layers'])]!=base['RootFS']['Layers']:
            raise ValueError('L’immagine non deriva dalla base software richiesta')
        config=loaded['Config'];baseconfig=base['Config']
        for field in ('Entrypoint','User','WorkingDir','Volumes','OnBuild','Healthcheck','Shell'):
            if config.get(field)!=baseconfig.get(field):raise ValueError('Configurazione di esecuzione non ammessa')
        allowed_env={item.split('=',1)[0] for item in baseconfig.get('Env',[])}|{
            'RIGHAVEN_CPU_THREADS','RIGHAVEN_MEMORY_MIB','TOKIO_WORKER_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS'}
        if any(item.split('=',1)[0] not in allowed_env for item in config.get('Env',[])):
            raise ValueError('Variabili di esecuzione non ammesse')
        expected_env={item.split('=',1)[0]:item for item in baseconfig.get('Env',[])}
        actual_env={item.split('=',1)[0]:item for item in config.get('Env',[])}
        if any(actual_env.get(name)!=value for name,value in expected_env.items()):raise ValueError('Base di esecuzione alterata')
        name='skill-import-'+uuid.uuid4().hex[:12];request=Path(directory)/'verify.json'
        atomic_json(request,{'tools':tools,'verify_only':True,'versions':versions,'version_packages':metadata.get('_version_packages',{})});request.chmod(0o644)
        cleaned=False
        from .resource_budget import BUDGET
        try:
            limits=BUDGET.acquire(name,'build',timeout=900)
            if on_progress:on_progress('checking_tools','Collaudo nativo dei programmi importati')
            args=base_arguments(name,limits)+runtime_arguments(skills=True)+[
                '--label','org.righaven.harness.installation='+factory.installation(),
                '--mount','type=bind,src='+host_path(request)+',dst=/environment-request.json,readonly',
                import_tag,'python3','/opt/righaven/prepare_environment.py','/environment-request.json']
            subprocess.run(['docker',*args],check=True,capture_output=True,text=True,timeout=900)
            if on_progress:on_progress('publishing','Salvataggio dell’ambiente importato e verificato')
            tag=factory.image_tag(key)
            identifier=factory.docker('commit','--change','LABEL org.righaven.environment='+key,
                '--change','LABEL org.righaven.harness.installation='+factory.installation(),
                '--change','CMD ["python3","-c","print(\\"Ambiente importato\\")"]',name,tag,timeout=900)
            details=json.loads(factory.docker('image','inspect',identifier))[0]
            remove(name);cleaned=True
            from .tool_versions import import_packages
            import_packages(versions,metadata.get('_version_packages',{}))
            return factory.save(key,status='ready',image=tag,image_id=details['Id'],size_bytes=details['Size'],
                core=spec['core'],tools=tools,versions=versions,version_names={t:b['app']['version'] for t,b in metadata.get('_version_packages',{}).items()},error='',container='',last_used=time.time(),imported=True)
        finally:
            if not cleaned:
                try:remove(name);cleaned=True
                except RuntimeError as exc:raise factory.PreparationCleanupError('Pulizia della verifica importazione non confermata') from exc
            if cleaned:BUDGET.release(name)
    finally:forget_tag(import_tag)
