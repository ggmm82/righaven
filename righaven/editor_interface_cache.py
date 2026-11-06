"""Interactive add-ons share the bounded software cache, never the draft lifetime."""
import fcntl
import json
import re
import subprocess
import time
from . import state


def folder():return state.STATE/'editor-interfaces'


def record(key):
    if not re.fullmatch(r'[a-f0-9]{64}',key):return None
    path=folder()/(key+'.json')
    if path.is_symlink() or not path.is_file() or path.stat().st_size>50000:return None
    try:
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) and value.get('image')=='righaven-editor:'+key else None
    except (OSError,ValueError):return None


def remember(key,tag,base,kind,packages=None,claim=None):
    from .environment_runtime import docker,installation,claim_environment
    inspected=json.loads(docker('image','inspect',tag))[0]
    if inspected.get('Config',{}).get('Labels',{}).get('org.righaven.harness.installation')!=installation():
        raise ValueError('Interactive software cache does not belong to this installation')
    previous=record(key) or {};now=time.time()
    value={'id':key,'editor_interface':True,'image':tag,'image_id':inspected['Id'],
           'base':base,'interface':kind,'packages':packages or previous.get('packages',[]),
           'created_at':previous.get('created_at',now),'last_used':now,'size_bytes':inspected.get('Size',0)}
    state.atomic_json(folder()/(key+'.json'),value)
    claim_environment({'id':key},claim)
    return value


def entries():
    if not folder().is_dir():return []
    result=[]
    for path in folder().glob('*.json'):
        value=record(path.stem)
        if value:
            # Older add-ons lacked disk/lifetime metadata. Observe it once and
            # enroll them in cleanup rather than leaving an unbounded old cache.
            if 'size_bytes' not in value:
                try:value=remember(path.stem,value['image'],value.get('base',''),value.get('interface',''))
                except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):continue
            result.append(value)
    return result


def evict(key):
    from .environment_runtime import docker,pinned,installation,_CACHE_LOCK
    value=record(key)
    if not value:return {'removed':False}
    with (folder()/(key+'.lock')).open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'removed':False}
        with _CACHE_LOCK:
            if key in pinned():return {'removed':False}
            inspected=json.loads(docker('image','inspect',value['image']))[0]
            if inspected['Id']!=value['image_id'] or inspected.get('Config',{}).get('Labels',{}).get('org.righaven.harness.installation')!=installation():return {'removed':False}
            if docker('ps','-aq','--filter','ancestor='+value['image_id']):return {'removed':False}
            docker('image','rm','--no-prune',value['image'],timeout=120)
            (folder()/(key+'.json')).unlink(missing_ok=True)
            return {'removed':True}
