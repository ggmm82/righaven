"""Bounded background transfer jobs, scoped to the requesting native account."""
import json
from pathlib import Path
import shutil
import threading
import time
import uuid

from . import state
from .state import atomic_json

LOCK=threading.Lock()


def root():
    directory=state.STATE/'environment-transfers';directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink():raise ValueError('Directory trasferimenti non valida')
    return directory


def read(user,identifier):
    if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise FileNotFoundError()
    directory=root()/identifier;file=directory/'status.json'
    if directory.is_symlink() or file.is_symlink() or not file.exists():raise FileNotFoundError()
    value=json.loads(file.read_text())
    if value.get('user')!=user:raise FileNotFoundError()
    return directory,value


def create(user,name,kind):
    with LOCK:
        active=[]
        for path in root().glob('*/status.json'):
            if path.is_symlink() or path.parent.is_symlink():continue
            value=json.loads(path.read_text())
            if value['state'] in ('ready','failed') and time.time()-value['updated_at']>86400:
                shutil.rmtree(path.parent);continue
            if value['state'] in ('uploading','working'):
                if value['user']==user and value['name']==name:raise ValueError('Un trasferimento per questo ambiente è già in corso')
                active.append(value)
        from .runtime_settings import effective
        if len(active)>=effective().get('max_workers',2):raise ValueError('Limite dei trasferimenti contemporanei raggiunto; attendi un completamento')
        identifier=uuid.uuid4().hex;directory=root()/identifier;directory.mkdir()
        value={'id':identifier,'user':user,'name':name,'kind':kind,'state':'uploading' if kind=='import' else 'working',
               'message':'Caricamento del pacchetto' if kind=='import' else 'Esportazione dell’immagine e della ricetta',
               'updated_at':time.time()}
        atomic_json(directory/'status.json',value)
        return directory,value


def for_user(user):
    result=[]
    for path in root().glob('*/status.json'):
        if path.is_symlink() or path.parent.is_symlink():continue
        value=json.loads(path.read_text())
        if value.get('user')==user and time.time()-value.get('updated_at',0)<86400:result.append(public(value,path.parent))
    return sorted(result,key=lambda v:v.get('updated_at',0),reverse=True)


def update(directory,**fields):
    value=json.loads((directory/'status.json').read_text());value.update(fields,updated_at=time.time())
    atomic_json(directory/'status.json',value)


def public(value,directory=None):
    result={k:v for k,v in value.items() if k in ('id','name','kind','state','message','updated_at','size_bytes','image_bytes','layer_count','phase','error_detail')}
    result['observed_at']=time.time()
    if directory is not None and value['state'] in ('working','uploading'):
        names={'exporting_image':'image.tar.raw','verifying_image':'image.tar','packaging':'environment.righaven-env.tar',
               'checking_package':'upload.tar','loading_image':'image.tar'}
        path=Path(directory)/names.get(value.get('phase'),'upload.tar' if value['state']=='uploading' else 'image.tar')
        try:
            if path.is_file() and not path.is_symlink():
                info=path.stat();result.update(bytes_written=info.st_size,last_output_at=info.st_mtime)
        except OSError:pass  # A phase may remove its temporary file between polls.
    if directory is not None and value['kind']=='export' and value['state']=='ready':
        archive=Path(directory)/'environment.righaven-env.tar'
        if not archive.is_file() or archive.is_symlink():
            result.update(state='failed',message='Il pacchetto non è più disponibile: esporta nuovamente l’ambiente')
    if value['kind']=='export' and value['state']=='ready' and value.get('image_validated') is not True:
        result.update(state='failed',message='Esportazione precedente non verificata: esporta nuovamente i programmi con la versione aggiornata')
    return result


def start(directory,work):
    def run():
        try:
            update(directory,state='working',message='Verifica e trasferimento dei programmi')
            result=work()
            update(directory,state='ready',message='Pacchetto pronto al download' if result else 'Ambiente importato e verificato',
                   size_bytes=Path(result).stat().st_size if result else 0)
        except Exception as exc:
            # Docker/native stderr can contain source details; publish only a bounded actionable error.
            import subprocess
            from .progress import clean_summary
            detail=getattr(exc,'detail','') or getattr(exc,'stderr','') or getattr(exc,'output','') or str(exc)
            message='Verifica o trasferimento Docker non riuscito; il pacchetto non è stato registrato' if isinstance(exc,subprocess.SubprocessError) else clean_summary(str(exc),400)
            import re
            detail=re.sub(r'(?i)(https?://)[^/\s]+@',r'\1[omesso]@',clean_summary(detail,2400))
            update(directory,state='failed',message=message,error_detail=detail)
        finally:
            successful=json.loads((directory/'status.json').read_text()).get('state')=='ready'
            for path in directory.iterdir():
                if path.name!='status.json' and not (successful and path.name=='environment.righaven-env.tar'):
                    if path.is_dir():shutil.rmtree(path)
                    else:path.unlink(missing_ok=True)
    threading.Thread(target=run,daemon=True,name='environment-transfer').start()


def recover():
    for path in root().glob('*/status.json'):
        if path.is_symlink() or path.parent.is_symlink():continue
        value=json.loads(path.read_text())
        if value['state'] in ('uploading','working'):
            update(path.parent,state='failed',message='Trasferimento interrotto dal riavvio; ripeti importazione o esportazione')
            for item in path.parent.iterdir():
                if item.name=='status.json':continue
                if item.is_dir():shutil.rmtree(item)
                else:item.unlink(missing_ok=True)


def active_images():
    result=set()
    for path in root().glob('*/status.json'):
        if path.is_symlink() or path.parent.is_symlink():continue
        value=json.loads(path.read_text())
        if value['state']=='working' and value.get('environment_id'):result.add(value['environment_id'])
    return result
