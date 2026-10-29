"""Verified model CLIs mounted independently of prepared application images."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from . import state

PROVIDERS={'codex':'codex','gemini':'agy','claude':'claude'}
TARGET='/opt/righaven/provider-overlay'
_CHECKED={}


def bundle_digest(root):
    digest=hashlib.sha256();size=0;count=0
    for path in sorted(root.rglob('*')):
        if path==root/'bundle.json':continue
        if path.is_symlink():
            if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Link CLI esterno al pacchetto')
            digest.update(path.relative_to(root).as_posix().encode()+b'->'+os.readlink(path).encode()+b'\0')
            continue
        if path.is_file():
            count+=1;size+=path.stat().st_size
            if count>30000 or size>2*1024**3:raise ValueError('Pacchetto CLI troppo grande')
            digest.update(path.relative_to(root).as_posix().encode()+b'\0')
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024**2),b''):digest.update(chunk)
    return digest.hexdigest()


def verified(root,key):
    if root.is_symlink() or not (root/'bundle.json').is_file():return None
    value=json.loads((root/'bundle.json').read_text())
    if value.get('id')!=key or value.get('binary') not in PROVIDERS.values() or not (root/'bin'/value['binary']).is_file():raise ValueError('Pacchetto CLI non valido')
    if _CHECKED.get(str(root))!=value.get('sha256'):
        if bundle_digest(root)!=value.get('sha256'):raise ValueError('Pacchetto CLI alterato')
        _CHECKED[str(root)]=value['sha256']
    return value


def prepare(engine,user=None,profile=None):
    """Prepare/export this CLI once; never install it into application environments."""
    binary=PROVIDERS.get(engine)
    if not binary:return None
    from . import tool_versions
    from .docker_runtime import docker
    from .environment_runtime import ensure,release_claim,installation
    selected=tool_versions.selections(engine=engine)
    selected={t:r for t,r in selected.items() if t=='provider-'+binary}
    pins=tool_versions.resolved(selected,wait=True,refresh=False)
    app=tool_versions.packages(pins).get('provider-'+binary,{}).get('app') or tool_versions.builtins()['provider-'+binary]
    basis={'engine':engine,'app':app,'pins':pins,'platform':__import__('platform').machine(),'schema':1}
    key=hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest()
    parent=state.STATE/'provider-bundles';parent.mkdir(parents=True,exist_ok=True)
    if parent.is_symlink():raise ValueError('Directory CLI non valida')
    destination=parent/key
    # A separate file lock also serializes publication across Gateway replicas.
    with (parent/(key+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        value=verified(destination,key)
        if value:
            if value['binary']!=binary or value['version']!=app['version']:raise ValueError('Metadati della CLI diversi dalla scelta corrente')
            return destination,value
        name='rh-provider-export-'+uuid.uuid4().hex[:12]
        temporary=Path(tempfile.mkdtemp(prefix='.staging-',dir=parent));created=False
        try:
            image=ensure([],versions=pins,claim=name)
            reference=image.get('image_id') or image.get('image')
            if not reference:
                from .docker_runtime import IMAGE
                reference=IMAGE
            docker('create','--name',name,'--pull=never','--network=none','--read-only','--cap-drop=ALL',
                   '--label','org.righaven.harness.installation='+installation(),reference,'true')
            created=True;(temporary/'bin').mkdir();(temporary/'lib').mkdir()
            if binary=='codex':
                source='/opt/righaven/provider-clis/codex/node_modules/@openai' if pins else '/usr/local/lib/node_modules/@openai'
                docker('cp','-L',name+':'+source,str(temporary/'lib/@openai'),timeout=180)
                entry=temporary/'lib/@openai/codex/bin/codex.js'
                if not entry.is_file():raise ValueError('Entrypoint Codex assente dal pacchetto')
                (temporary/'bin/codex').write_text('#!/bin/sh\nexec node '+TARGET+'/lib/@openai/codex/bin/codex.js "$@"\n')
                (temporary/'bin/codex').chmod(0o755)
            else:
                source='/opt/righaven/provider-clis/'+binary+'/'+binary if pins else '/usr/local/bin/'+binary
                docker('cp','-L',name+':'+source,str(temporary/'bin'/binary),timeout=180)
                (temporary/'bin'/binary).chmod(0o755)
            value={'id':key,'binary':binary,'version':app['version'],'sha256':bundle_digest(temporary)}
            state.atomic_json(temporary/'bundle.json',value)
            for path in temporary.rglob('*'):
                if path.is_dir():path.chmod(0o755)
                elif path.is_file():path.chmod(0o755 if os.access(path,os.X_OK) else 0o644)
            temporary.chmod(0o755);temporary.rename(destination)
            _CHECKED[str(destination)]=value['sha256']
            return destination,value
        finally:
            if temporary.exists():shutil.rmtree(temporary)
            try:
                if created:
                    from .docker_runtime import remove
                    remove(name)
            finally:release_claim(name)


def arguments(bundle):
    if not bundle:return []
    from .docker_runtime import mount
    root,value=bundle
    return ['--mount',mount(root,TARGET,True),'--env','PATH='+TARGET+'/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin']
