"""Bounded, metadata-only navigation of an owned conversation's public files."""
import json
import os
from pathlib import Path
import stat
import time
from .editor_documents import relative

ROOTS=('uploads','outputs','workspace')
MAX_VISITED=10000


def labels(workspace):
    path=Path(workspace)/'.righaven-project/project.json';result={}
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size>1000000:return result
    try:value=json.loads(path.read_text())
    except (ValueError,OSError):return result
    if not isinstance(value,dict) or not isinstance(value.get('steps',[]),list):return result
    for step in value.get('steps',[]):
        if not isinstance(step,dict) or not isinstance(step.get('attempts',[]),list):continue
        for attempt in step.get('attempts',[]):
            if not isinstance(attempt,dict):continue
            record=attempt.get('delivery_record') or {}
            if not isinstance(record,dict) or not isinstance(record.get('files',[]),list):continue
            for item in record.get('files',[]):
                if not isinstance(item,dict):continue
                path=item.get('path','')
                if isinstance(path,str) and path.startswith('/mnt/user-data/'):
                    result[path]={'role':item.get('role','working_file'),'delivery_id':str(record.get('id') or attempt.get('delivery_id') or '')[:200],'delivery':str(record.get('title') or step.get('goal') or '')[:200]}
    return result


def folder_summary(root,path,budget):
    """Logical size of visible files, bounded across this entire listing page."""
    result={'size':0,'file_count':0,'size_complete':True};fd=None
    def walk(directory,depth):
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if budget['remaining']<=0 or time.monotonic()>budget['deadline']:
                        result['size_complete']=False;return
                    budget['remaining']-=1
                    if entry.name.startswith('.') or entry.name in ('node_modules','__pycache__','venv'):continue
                    try:
                        info=entry.stat(follow_symlinks=False)
                        if stat.S_ISREG(info.st_mode):result['size']+=info.st_size;result['file_count']+=1
                        elif stat.S_ISDIR(info.st_mode):
                            if depth>=24:result['size_complete']=False;continue
                            child=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
                            try:walk(child,depth+1)
                            finally:os.close(child)
                    except OSError:result['size_complete']=False
                    if not result['size_complete'] and (budget['remaining']<=0 or time.monotonic()>budget['deadline']):return
        except OSError:result['size_complete']=False
    if budget['remaining']<=0 or time.monotonic()>budget['deadline']:
        result['size_complete']=False;return result
    try:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        for part in path.split('/'):
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        walk(fd,0)
    except OSError:result['size_complete']=False
    finally:
        if fd is not None:os.close(fd)
    return result


def listing(workspace,path='',query='',role='all',offset=0,limit=150):
    """Directory FDs prevent workers replacing a folder with an external symlink."""
    if path:
        path=relative(path)
        if path.split('/')[0] not in ROOTS:raise ValueError('Choose an attachment or project output')
    if not isinstance(query,str) or len(query)>200 or not 0<=offset<=MAX_VISITED or not 1<=limit<=300:raise ValueError('Invalid document path')
    root=Path(workspace).resolve();refs=labels(root);rows=[];visited=0;truncated=False;query=query.strip().casefold()
    try:root_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    except FileNotFoundError:
        if path:raise ValueError('Document file not found') from None
        return {'path':'','entries':[],'next_offset':None,'truncated':False,'scope':'conversation'}
    def scan(fd,prefix,depth):
        nonlocal visited,truncated
        try:
            with os.scandir(fd) as entries:
                for entry in entries:
                    visited+=1
                    if visited>MAX_VISITED:truncated=True;return
                    if entry.name.startswith('.') or entry.name in ('node_modules','__pycache__','venv'):continue
                    try:info=entry.stat(follow_symlinks=False)
                    except OSError:continue
                    directory=stat.S_ISDIR(info.st_mode)
                    if not directory and not stat.S_ISREG(info.st_mode):continue
                    name=prefix+'/'+entry.name if prefix else entry.name
                    if not prefix and entry.name not in ROOTS:continue
                    virtual='/mnt/user-data/'+name
                    details=refs.get(virtual,{'role':'attachment' if name.startswith('uploads/') else 'revision' if name.startswith('outputs/source-revisions/') else 'working_file','delivery_id':''})
                    if (not query or query in name.casefold()) and (role=='all' or details['role']==role or directory):
                        rows.append({'name':entry.name,'path':name,'virtual_path':virtual,'directory':directory,'size':None if directory else info.st_size,'modified_at':info.st_mtime,**details})
                    if query and directory and depth>=24:truncated=True
                    if query and directory and depth<24:
                        child=None
                        try:
                            child=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);scan(child,name,depth+1)
                        except OSError:pass
                        finally:
                            if child is not None:os.close(child)
                    if visited>MAX_VISITED:return
        except OSError:truncated=True
    fd=os.dup(root_fd)
    try:
        for part in path.split('/') if path else []:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        scan(fd,path,0)
    except OSError:raise ValueError('Document file not found') from None
    finally:os.close(fd);os.close(root_fd)
    rows.sort(key=lambda item:(not item['directory'],item['path'].casefold()))
    page=rows[offset:offset+limit];budget={'remaining':2500,'deadline':time.monotonic()+.075}
    for row in page:
        if row['directory']:row.update(folder_summary(root,row['path'],budget))
    return {'path':path,'entries':page,'next_offset':offset+limit if len(rows)>offset+limit else None,'truncated':truncated,'scope':'conversation'}
