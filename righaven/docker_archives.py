"""Complete single-platform Docker archives, independent of the image-store backend.

Containerd may identify images by OCI manifest digest rather than config digest.
Always export by reference/platform, verify every referenced blob and diff ID, and
normalize into a tagless Docker archive. Never trust the exit code of `save` alone.
This module is also shipped beside the standalone rebuild packager.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import uuid

MAX_BYTES=16*1024**3


def _members(archive):
    result={}
    for member in archive:
        path=Path(member.name)
        if (len(result)>=10000 or member.name in result or path.is_absolute() or '..' in path.parts
                or '\\' in member.name or not (member.isfile() or member.isdir())):
            raise ValueError('Archivio immagine Docker non valido')
        result[member.name]=member
    return result


def _json(archive,members,name,maximum=1024**2):
    entry=members.get(name)
    if not entry or not entry.isfile():raise ValueError('Immagine Docker incompleta: manca '+name)
    if entry.size>maximum:raise ValueError('Metadati immagine troppo grandi')
    data=archive.extractfile(entry).read()
    try:return json.loads(data),data
    except ValueError as exc:raise ValueError('Metadati immagine non validi') from exc


def metadata(archive,members,*,untagged=False):
    images,_=_json(archive,members,'manifest.json',64000)
    if not isinstance(images,list) or len(images)!=1 or not isinstance(images[0],dict):
        raise ValueError('Occorre una sola immagine nel pacchetto')
    image=images[0]
    if untagged and image.get('RepoTags'):raise ValueError('Occorre una sola immagine senza tag nel pacchetto')
    config,data=_json(archive,members,image.get('Config',''))
    config_id='sha256:'+hashlib.sha256(data).hexdigest()
    layers=image.get('Layers');diffs=(config.get('rootfs') or {}).get('diff_ids')
    if (not isinstance(layers,list) or not isinstance(diffs,list) or len(layers)!=len(diffs)
            or not layers or len(layers)>512 or any(not isinstance(p,str) for p in layers)):
        raise ValueError('Manifest dei livelli Docker non valido')
    for name in layers:
        if name not in members or not members[name].isfile():
            raise ValueError('Immagine Docker incompleta: mancano i livelli con i programmi')
    if untagged and 'repositories' in members:
        repos,_=_json(archive,members,'repositories',64000)
        if repos:raise ValueError('Il pacchetto non può sovrascrivere tag locali')
    if untagged and 'index.json' in members:
        index,_=_json(archive,members,'index.json',64000)
        for item in index.get('manifests',[]):
            ref=item.get('annotations',{}).get('org.opencontainers.image.ref.name')
            if ref and ref not in (config_id,config_id.removeprefix('sha256:')):
                raise ValueError('Il pacchetto non può sovrascrivere tag locali')
    return {'config':config,'config_bytes':data,'config_digest':config_id,'layers':layers,'diff_ids':diffs}


def _layer(archive,member,expected,output=None,budget=MAX_BYTES):
    digest=hashlib.sha256();size=0
    with archive.extractfile(member) as raw:
        magic=raw.read(2);raw.seek(0)
        source=gzip.GzipFile(fileobj=raw) if magic==b'\x1f\x8b' else raw
        try:
            while chunk:=source.read(1024**2):
                size+=len(chunk)
                if size>budget:raise ValueError('Immagine espansa oltre il limite di 16 GiB')
                digest.update(chunk)
                if output:output.write(chunk)
        finally:
            if source is not raw:source.close()
    if 'sha256:'+digest.hexdigest()!=expected:raise ValueError('Checksum di un livello Docker non valido')
    return size


def validate(path,*,expected_config=None,untagged=True):
    with tarfile.open(path,'r:') as archive:
        members=_members(archive);info=metadata(archive,members,untagged=untagged)
        if expected_config and info['config_digest']!=expected_config:raise ValueError('Identità Docker non valida')
        total=0
        for name,diff in zip(info['layers'],info['diff_ids']):
            total+=_layer(archive,members[name],diff,budget=MAX_BYTES-total)
    return info


def _add(archive,name,data):
    entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o644
    archive.addfile(entry,io.BytesIO(data))


def normalize(source,destination,*,expected_layers=None):
    """OCI/gzipped or classic Docker save -> complete tagless, uncompressed archive."""
    destination=Path(destination)
    try:
        with tarfile.open(source,'r:') as original,tarfile.open(destination,'w') as target:
            members=_members(original);info=metadata(original,members)
            if expected_layers is not None and info['diff_ids']!=expected_layers:
                raise ValueError('L’esportazione non contiene i livelli dell’immagine richiesta')
            config_name=info['config_digest'].removeprefix('sha256:')+'.json'
            _add(target,config_name,info['config_bytes'])
            names=[];total=0
            with tempfile.TemporaryFile(dir=destination.parent) as temporary:
                for index,(name,diff) in enumerate(zip(info['layers'],info['diff_ids'])):
                    temporary.seek(0);temporary.truncate()
                    size=_layer(original,members[name],diff,temporary,MAX_BYTES-total);total+=size
                    temporary.seek(0);name='layers/'+str(index)+'/layer.tar';names.append(name)
                    entry=tarfile.TarInfo(name);entry.size=size;entry.mode=0o644
                    target.addfile(entry,temporary)
            _add(target,'manifest.json',json.dumps([{'Config':config_name,'RepoTags':None,'Layers':names}]).encode())
        return info
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


class ImageExportError(RuntimeError):
    def __init__(self,detail):
        super().__init__('Docker non ha completato l’esportazione dell’immagine')
        self.detail=detail


def save_image(reference,details,destination,on_progress=None):
    destination=Path(destination);raw=destination.with_name(destination.name+'.raw')
    platform=details['Os']+'/'+details['Architecture']+('/'+details['Variant'] if details.get('Variant') else '')
    export_tag='skill-export:'+uuid.uuid4().hex
    try:
        if on_progress:on_progress('exporting_image','Esportazione dei livelli dell’immagine Docker')
        subprocess.run(['docker','image','tag',reference,export_tag],check=True,capture_output=True,timeout=60)
        command=['docker','image','save','--platform',platform,'--output',str(raw),export_tag]
        result=subprocess.run(command,capture_output=True,text=True,timeout=1800)
        if result.returncode:
            # Docker stores differ in support for platform selection, including
            # single-platform images not indexed by the daemon. One tag-only
            # retry is safe: normalization still checks every expected layer,
            # OS and architecture before the archive can be offered.
            first=result.stderr
            raw.unlink(missing_ok=True)
            if on_progress:on_progress('exporting_image','Esportazione compatibile con la versione Docker del server')
            result=subprocess.run(['docker','image','save','--output',str(raw),export_tag],capture_output=True,text=True,timeout=1800)
            if result.returncode:raise ImageExportError(first+'\nTentativo compatibile:\n'+result.stderr)
        if on_progress:on_progress('verifying_image','Verifica dei livelli e dei checksum dell’immagine')
        info=normalize(raw,destination,expected_layers=details['RootFS']['Layers'])
        if info['config'].get('os')!=details['Os'] or info['config'].get('architecture')!=details['Architecture']:
            raise ValueError('Piattaforma dell’immagine esportata diversa da quella richiesta')
        return info
    finally:
        raw.unlink(missing_ok=True)
        forget_tag(export_tag)


def load_image(path,directory):
    """Load through a private random tag; engine-specific IDs are never assumed."""
    tag='skill-transfer:'+uuid.uuid4().hex
    temporary=Path(directory)/'load-image.tar'
    try:
        with tarfile.open(path,'r:') as source,tarfile.open(temporary,'w') as target:
            for member in source:
                if member.name=='manifest.json':
                    images=json.load(source.extractfile(member));images[0]['RepoTags']=[tag]
                    _add(target,'manifest.json',json.dumps(images).encode())
                elif member.isfile():target.addfile(member,source.extractfile(member))
                else:target.addfile(member)
        subprocess.run(['docker','image','load','--input',str(temporary)],check=True,capture_output=True,text=True,timeout=1800)
        details=json.loads(subprocess.check_output(['docker','image','inspect',tag],text=True))[0]
        return tag,details
    except BaseException:
        subprocess.run(['docker','image','rm','--no-prune',tag],capture_output=True)
        raise
    finally:temporary.unlink(missing_ok=True)


def forget_tag(tag):
    subprocess.run(['docker','image','rm','--no-prune',tag],capture_output=True,timeout=60)
