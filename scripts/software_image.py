#!/usr/bin/env python3
"""Persistent software reuse by content, independent of GitHub's branch build cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

BOUNDARY = 'FROM software AS core'


def inputs(root, platform='linux/amd64'):
    root = Path(root)
    dockerfile = (root/'docker/Dockerfile.sandbox').read_text()
    if dockerfile.count(BOUNDARY) != 1:
        raise ValueError('Separazione software/worker non riconosciuta')
    software = dockerfile.split(BOUNDARY)[0]
    if not re.search(r'^FROM node:[^\s]+@sha256:[a-f0-9]{64} AS software$', software, re.M):
        raise ValueError('La base Node deve essere fissata con digest immutabile')
    files = {}
    for line in software.splitlines():
        if not line.startswith('COPY '): continue
        arguments = shlex.split(line)[1:]
        if any(a.startswith('--') for a in arguments):
            raise ValueError('COPY software non supportato: dichiarare esplicitamente gli input')
        for source in arguments[:-1]:
            path = root/source
            if not path.exists() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Input software mancante o non valido: '+source)
            entries = sorted(path.rglob('*')) if path.is_dir() else [path]
            for entry in entries:
                if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
                    raise ValueError('Input software non regolare')
                if entry.is_file():
                    files[str(entry.relative_to(root))] = hashlib.sha256(entry.read_bytes()).hexdigest()
    return {'version':1, 'platform':platform, 'dockerfile':hashlib.sha256(software.encode()).hexdigest(), 'files':files}


def fingerprint(root, platform='linux/amd64'):
    return hashlib.sha256(json.dumps(inputs(root,platform),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def repository(value):
    if not re.fullmatch(r'[a-z0-9_.-]+/[a-z0-9_.-]+',value):raise ValueError('Repository non valido')
    return 'ghcr.io/'+value+'-sandbox'


def digest(reference):
    result=subprocess.run(['docker','buildx','imagetools','inspect',reference],
                          text=True,capture_output=True,timeout=120)
    if result.returncode:
        if re.search(r'(?i)manifest unknown|name unknown|\bnot found\b',result.stderr):return None
        raise RuntimeError('Registro non raggiungibile o accesso non autorizzato; non ricostruisco una base per un errore di rete')
    matches=re.findall(r'^Digest:\s*(sha256:[a-f0-9]{64})\s*$',result.stdout,re.M)
    if len(matches)!=1:raise ValueError('Digest del registro non valido')
    return matches[0]


def resolve(root, repo, platform='linux/amd64'):
    if platform not in ('linux/amd64','linux/arm64'):raise ValueError('Piattaforma non supportata')
    key=fingerprint(root,platform); image_repository=repository(repo)
    reference=image_repository+':software-'+key
    lock=json.loads((Path(root)/'config/software-image.lock.json').read_text())
    bootstrap=lock.get('bootstrap',{})
    image=''
    if bootstrap.get('fingerprint')==key and bootstrap.get('platform')==platform:
        image=bootstrap['image']
        if not re.fullmatch(r'ghcr.io/[a-z0-9_.-]+/[a-z0-9_.-]+@sha256:[a-f0-9]{64}',image):
            raise ValueError('Immagine iniziale non valida')
    else:
        found=digest(reference)
        if found:image=image_repository+'@'+found
    return {'fingerprint':key,'tag':reference,'image':image,'reuse':bool(image),
            'context':'software=docker-image://'+image if image else ''}


def publish(value, image):
    image_repository=value['tag'].split(':software-')[0]
    expected=image.split('@',1)[1] if '@' in image else digest(image)
    if not expected or not re.fullmatch(r'sha256:[a-f0-9]{64}',expected):raise ValueError('Immagine verificata priva di digest')
    existing=digest(value['tag'])
    if existing:
        if existing!=expected:raise ValueError('La stessa ricetta ha già una base diversa: non sovrascrivo la versione pubblicata')
        return
    subprocess.run(['docker','buildx','imagetools','create','--prefer-index=false','--tag',value['tag'],image_repository+'@'+expected],check=True,timeout=180)
    if digest(value['tag'])!=expected:
        raise ValueError('Il registro ha cambiato il manifest software')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['resolve','publish','fingerprint'])
    parser.add_argument('--root',type=Path,default=Path('.'));parser.add_argument('--repository',default=os.getenv('GITHUB_REPOSITORY','righaven/righaven').lower())
    parser.add_argument('--platform',default='linux/amd64');parser.add_argument('--image')
    parser.add_argument('--state',type=Path,default=Path('reports/software-image.json'))
    args=parser.parse_args()
    if args.action=='fingerprint':print(fingerprint(args.root,args.platform));return
    if args.action=='publish':
        publish(json.loads(args.state.read_text()),args.image);return
    value=resolve(args.root,args.repository,args.platform)
    args.state.parent.mkdir(parents=True,exist_ok=True);args.state.write_text(json.dumps(value,indent=2)+'\n')
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
            for key in ('reuse','image','context','fingerprint'):
                entry=str(value[key]).lower() if isinstance(value[key],bool) else value[key]
                stream.write(key+'='+entry+'\n')
    print('Software invariato: riuso immagine pubblicata '+value['image'] if value['reuse'] else 'Programmi o dipendenze cambiati: nuova base software richiesta')


if __name__=='__main__':main()
