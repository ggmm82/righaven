"""Lazy web packages: fixed upstreams, verified digests, bounded immutable cache."""
import fcntl
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import shutil
import tempfile
import threading
import urllib.request
import zipfile
from . import state
from .editor_catalog import CRAFT
from .progress import utcnow

LOCK=threading.RLock()
JOBS={}


def location(tool,version):
    version=version.removeprefix('v')
    if tool not in CRAFT or not re.fullmatch(r'[0-9][0-9A-Za-z.+_-]{0,60}',version):raise ValueError('Invalid browser editor package')
    return state.STATE/'editor-assets'/tool/version


def status(tool,version):
    version=version.removeprefix('v')
    root=location(tool,version);path=root/'package.json'
    if path.is_file() and not path.is_symlink():return json.loads(path.read_text())
    with LOCK:return dict(JOBS.get((tool,version),{'state':'not_prepared','editor':tool,'version':version}))


def request(tool,version):
    version=version.removeprefix('v')
    location(tool,version)
    with LOCK:
        current=status(tool,version)
        if current['state'] in ('ready','preparing'):return current
        JOBS[tool,version]={'state':'preparing','editor':tool,'version':version,'message':'Checking upstream browser release'}
        threading.Thread(target=prepare,args=(tool,version),daemon=True,name='editor-assets-'+tool).start()
        return dict(JOBS[tool,version])


def download(url,limit):
    req=urllib.request.Request(url,headers={'User-Agent':'RigHaven-editor-packages'})
    with urllib.request.urlopen(req,timeout=60) as stream:
        if int(stream.headers.get('Content-Length','0'))>limit:raise ValueError('Editor download exceeds size limits')
        data=stream.read(limit+1)
        if len(data)>limit:raise ValueError('Editor download exceeds size limits')
        return data


def extract(archive,target):
    with zipfile.ZipFile(archive) as bundle:
        entries=bundle.infolist();names=[PurePosixPath(v.filename) for v in entries]
        if len(entries)>5000 or sum(v.file_size for v in entries)>512*1024*1024:raise ValueError('Editor archive exceeds extraction limits')
        for item,name in zip(entries,names):
            if not name.parts or name.is_absolute() or '..' in name.parts or '\\' in item.filename or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Invalid editor archive path')
        strip=len({p.parts[0] for p in names})==1 and not any(str(p)=='index.html' for p in names)
        for item,name in zip(entries,names):
            relative=PurePosixPath(*name.parts[1:]) if strip else name
            if item.is_dir() or str(relative)=='.':continue
            path=target/str(relative);path.parent.mkdir(parents=True,exist_ok=True)
            with bundle.open(item) as src,path.open('xb') as dst:shutil.copyfileobj(src,dst)
    if not (target/'index.html').is_file():raise ValueError('Editor package has no entry page')


def prepare(tool,version):
    version=version.removeprefix('v')
    root=location(tool,version);temporary=None
    try:
        root.parent.mkdir(parents=True,exist_ok=True)
        with (root.parent/(version+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if (root/'package.json').is_file():return
            release=json.loads(download(f'https://api.github.com/repos/storytold/{tool}/releases/tags/v{version}',4*1024*1024))
            name=f'{tool}-web-{version}.zip';asset=next((v for v in release.get('assets',[]) if v['name']==name),None)
            if not asset or not re.fullmatch(r'sha256:[a-f0-9]{64}',asset.get('digest') or ''):raise ValueError('Release has no checksum-verified browser editor')
            url=f'https://github.com/storytold/{tool}/releases/download/v{version}/{name}'
            if asset['browser_download_url']!=url:raise ValueError('Unexpected browser package URL')
            with LOCK:JOBS[tool,version]['message']='Downloading and verifying browser editor'
            temporary=Path(tempfile.mkdtemp(prefix=version+'-',dir=root.parent));data=download(url,128*1024*1024);sha=hashlib.sha256(data).hexdigest()
            if sha!=asset['digest'].split(':')[1]:raise ValueError('Browser editor checksum mismatch')
            archive=temporary/'web.zip';archive.write_bytes(data);web=temporary/'assets';web.mkdir();extract(archive,web);archive.unlink()
            state.atomic_json(temporary/'package.json',{'state':'ready','editor':tool,'version':version,'sha256':sha,'source':url,'updated_at':utcnow(),'size_bytes':sum(p.stat().st_size for p in web.rglob('*') if p.is_file())})
            if root.exists():shutil.rmtree(root)
            temporary.rename(root);temporary=None
    except Exception as error:
        with LOCK:JOBS[tool,version]={'state':'failed','editor':tool,'version':version,'message':str(error)[:600]}
    finally:
        if temporary:shutil.rmtree(temporary,ignore_errors=True)


def file(tool,version,name):
    version=version.removeprefix('v')
    root=location(tool,version)/'assets';path=root/name
    if status(tool,version)['state']!='ready' or not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Browser editor asset not prepared')
    return path
