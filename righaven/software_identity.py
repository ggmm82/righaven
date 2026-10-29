"""Software compatibility and per-tool identities, independent of code and providers."""
import hashlib
import json
import os
from pathlib import Path
import threading

_LOCK=threading.RLock()
_CACHE={}
POLICY=1
FIELDS=('id','version','assets','install','resources','binary','binary_paths','executable')


def lock_paths(tool):
    paths=['python/'+tool+'.txt','design/'+tool+'/package.json','design/'+tool+'/package-lock.json']
    if tool=='playwright':paths=['package.json','package-lock.json']
    if tool=='structurizr':paths=['design/structurizr/libraries.json']
    if tool=='axe-core':paths=['extended/axe-core/package.json','extended/axe-core/package-lock.json']
    return paths


def fingerprint(app,root):
    value={k:app[k] for k in FIELDS if k in app}
    value['files']={name:(Path(root)/name).read_text() for name in lock_paths(app['id']) if (Path(root)/name).is_file()}
    mapping=Path(root)/'system-packages.json'
    value['system_packages']=json.loads(mapping.read_text()).get(app['id'],[]) if mapping.is_file() else []
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


# Runs only in a trusted software image, without accounts, project mounts or network.
PROBE = r'''import hashlib,json,platform,subprocess
from pathlib import Path
packages=['libc6','libstdc++6','libssl3','zlib1g','python3-minimal','libpython3.11-minimal']
versions=subprocess.check_output(['dpkg-query','-W','-f=${Package}=${Version}\n',*packages],text=True).splitlines()
abi={'schema':1,'platform':platform.machine(),'os':Path('/etc/os-release').read_text(),'packages':sorted(versions),'node':subprocess.check_output(['node','--version'],text=True).strip()}
r=Path('/opt/righaven');catalog=json.loads((r/'catalog.lock.json').read_text());installed=json.loads((r/'installed.json').read_text());names={x['id'] for x in installed}
def paths(tool):
 p=['python/'+tool+'.txt','design/'+tool+'/package.json','design/'+tool+'/package-lock.json']
 if tool=='playwright':p=['package.json','package-lock.json']
 if tool=='structurizr':p=['design/structurizr/libraries.json']
 if tool=='axe-core':p=['extended/axe-core/package.json','extended/axe-core/package-lock.json']
 return p
fingerprints={}
for app in catalog['applications']:
 value={k:app[k] for k in ('id','version','assets','install','resources','binary','binary_paths','executable') if k in app}
 value['files']={n:(r/'toolkit-lock'/n).read_text() for n in paths(app['id']) if (r/'toolkit-lock'/n).is_file()}
 mapping=r/'toolkit-lock/system-packages.json';value['system_packages']=json.loads(mapping.read_text()).get(app['id'],[]) if mapping.is_file() else []
 fingerprints[app['id']]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps({'abi':hashlib.sha256(json.dumps(abi,sort_keys=True).encode()).hexdigest(),'fingerprints':{k:v for k,v in fingerprints.items() if k in names},'catalog_fingerprints':fingerprints,'catalog_versions':{a['id']:a['version'] for a in catalog['applications']}}))
'''


def inspect(image,docker):
    """Persistent immutable-image cache; failure preserves strict image matching."""
    if not isinstance(image,str) or not image.startswith('sha256:'):return None
    from . import state
    key=hashlib.sha256(image.encode()).hexdigest();path=state.STATE/'software-identities'/(key+'.json')
    with _LOCK:
        if image in _CACHE:return _CACHE[image]
        if path.is_file() and not path.is_symlink():
            try:
                value=json.loads(path.read_text())
                if value.get('policy')==POLICY and value.get('image')==image and isinstance(value.get('abi'),str) and len(value['abi'])==64 and isinstance(value.get('fingerprints'),dict):
                    _CACHE[image]=value;return value
            except (OSError,ValueError):pass
        try:
            output=docker('run','--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                '--pids-limit=32','--memory=128m','--cpus=.25','--entrypoint','python3',image,'-c',PROBE,timeout=45)
            value=json.loads(output)
            if not isinstance(value,dict) or not isinstance(value.get('abi'),str) or len(value['abi'])!=64 or not isinstance(value.get('fingerprints'),dict):return None
            value.update(image=image,policy=POLICY)
            state.atomic_json(path,value);_CACHE[image]=value
            return value
        except (OSError,ValueError,RuntimeError,__import__('subprocess').SubprocessError):return None


def cached(image):
    with _LOCK:return _CACHE.get(image)


def planned(tools,versions):
    from . import state,tool_versions
    builtin={app['id']:app for app in state.applications()};root=Path(os.getenv('RIGHAVEN_WORKER_SOURCE',Path(__file__).resolve().parents[1]))/'config/toolkit'
    result={};names={}
    for tool in tools:
        if tool in (versions or {}):
            bundle=tool_versions.read(versions[tool])['bundle']
            # Hash the software inputs, excluding editorial catalog metadata.
            app=bundle['app'];value={k:app[k] for k in FIELDS if k in app}
            files=bundle.get('files',{})
            value['files']={name:files.get('toolkit-lock/'+name,(root/name).read_text() if (root/name).is_file() else '') for name in lock_paths(tool) if 'toolkit-lock/'+name in files or (root/name).is_file()}
            mapping=root/'system-packages.json'
            value['system_packages']=json.loads(mapping.read_text()).get(tool,[]) if mapping.is_file() else []
            result[tool]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        else:
            app=builtin[tool];result[tool]=fingerprint(app,root)
        names[tool]=app['version']
    return result,names


def compatible(value,spec,docker):
    if value.get('core')==spec['core']:return True
    if not spec.get('software_abi'):return False
    actual=value.get('software_abi')
    if not actual:
        info=inspect(value.get('core'),docker) or inspect(value.get('image_id'),docker)
        actual=info.get('abi') if info else None
    return actual==spec['software_abi']


def inherited_fingerprints(value,spec,docker):
    if value.get('tool_fingerprints') is not None:return value['tool_fingerprints']
    if spec.get('software_abi'):
        base=inspect(value.get('core'),docker) or {}
        actual={};observed=value.get('installed_versions') or {}
        for tool in value.get('tools',[]):
            pin=value.get('versions',{}).get(tool)
            if pin and pin==spec.get('versions',{}).get(tool):
                actual[tool]=spec.get('tool_fingerprints',{}).get(tool)
            elif not pin and observed.get(tool)==base.get('catalog_versions',{}).get(tool) and tool in base.get('catalog_fingerprints',{}):
                actual[tool]=base['catalog_fingerprints'][tool]
            else:
                info=inspect(value.get('image_id'),docker)
                return info.get('fingerprints',{}) if info else {}
        return actual
    return None  # Legacy test/import descriptors without a compatibility identity.


def catalog_files(tools):
    root=Path(os.getenv('RIGHAVEN_WORKER_SOURCE',Path(__file__).resolve().parents[1]))/'config/toolkit'
    paths={'system-packages.json'}
    for tool in tools:paths.update(lock_paths(tool))
    return {'toolkit-lock/'+name:(root/name).read_text() for name in sorted(paths) if (root/name).is_file()}
