"""Official release discovery; users select versions, never installation commands."""
import copy
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

VERSION=re.compile(r'[0-9A-Za-z][0-9A-Za-z.+:~_-]{0,100}\Z')
NPM={'playwright':'@playwright/test','mermaid':'@mermaid-js/mermaid-cli','excalidraw':'@excalidraw/excalidraw','bpmn':'bpmn-to-image','provider-codex':'@openai/codex','axe-core':'@axe-core/playwright'}
PYPI={'ifcopenshell':'ifcopenshell','manim':'manim','opentimelineio':'opentimelineio','pymeshlab':'pymeshlab','schemathesis':'schemathesis'}


def read(url,limit=8*1024**2,accept="application/json"):
    if not url.startswith('https://'):raise ValueError('Sono ammesse solo fonti ufficiali HTTPS')
    req=urllib.request.Request(url,headers={'User-Agent':'RigHaven-version-manager','Accept':accept})
    with urllib.request.urlopen(req,timeout=60) as response:
        value=response.read(limit+1)
    if len(value)>limit:raise ValueError('Risposta del registro troppo grande')
    return value


def data(url):return json.loads(read(url))


def sha_asset(url,provided=None):
    if isinstance(provided,str) and re.fullmatch(r'sha256:[a-f0-9]{64}',provided):return provided[7:],None
    value=hashlib.sha256();size=0
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RigHaven-version-manager'}),timeout=120) as response:
        while chunk:=response.read(1024**2):
            size+=len(chunk)
            if size>2*1024**3:raise ValueError('Distribuzione superiore a 2 GiB')
            value.update(chunk)
    return value.hexdigest(),size


def gh_repository(app):
    match=re.fullmatch(r'https://github.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)',app['repository'])
    return match[1] if match else None


def prerelease(version):
    return bool(re.search(r"(?:alpha|beta|preview|nightly|snapshot|canary|experimental|next|dev|rc|pre[0-9]|(?:[0-9.])[abc][0-9]|-m[0-9]|-pre)",version,re.I))


def options(app):
    tool=app['id'];source=gh_repository(app)
    if tool=='verapdf':
        index=read('https://software.verapdf.org/releases/').decode()
        families=sorted(set(re.findall(r'href="([0-9]+\.[0-9]+)/"',index)),key=lambda s:tuple(map(int,s.split('.'))))[-3:]
        versions=[]
        for family in families:
            page=read('https://software.verapdf.org/releases/'+family+'/').decode()
            versions.extend(re.findall(r'verapdf-greenfield-([0-9]+\.[0-9]+\.[0-9]+)-installer.zip"',page))
        latest=None
    elif tool in NPM:
        result=json.loads(read('https://registry.npmjs.org/'+urllib.parse.quote(NPM[tool],safe='@/'),32*1024**2,accept='application/vnd.npm.install-v1+json'))
        versions=list(result.get('versions',{}));latest=result.get('dist-tags',{}).get('latest')
    elif tool in PYPI:
        result=data('https://pypi.org/pypi/'+PYPI[tool]+'/json');versions=list(result['releases']);latest=result['info']['version']
    elif tool=='blender':
        text=read('https://download.blender.org/release/',4*1024**2).decode()
        folders=sorted(set(re.findall(r'href="(Blender[0-9.]+/)"',text)),key=lambda v:tuple(map(int,re.findall(r'\d+',v))))[-5:];versions=[]
        for folder in folders:
            versions+=re.findall(r'blender-([0-9]+\.[0-9]+\.[0-9]+)-linux-x64',read('https://download.blender.org/release/'+folder,4*1024**2).decode())
        latest=None
    elif tool=='structurizr':
        root=ET.fromstring(read('https://repo.maven.apache.org/maven2/com/structurizr/structurizr-dsl/maven-metadata.xml'))
        versions=[v.text for v in root.findall('.//version')];latest=root.findtext('.//release')
    elif app.get('install',{}).get('kind')=='debian':
        versions=[app['version'],*{a.get('package_version') for a in app['assets'].values()}];latest=None
    elif source:
        endpoint='/tags' if tool=='ffmpeg' else '/releases'
        result=data('https://api.github.com/repos/'+source+endpoint+'?per_page=30')
        if not result and endpoint=='/releases':result=data('https://api.github.com/repos/'+source+'/tags?per_page=30')
        return [{'version':r.get('tag_name') or r['name'],'prerelease':r.get('prerelease',False) or prerelease(r.get('tag_name') or r['name'])} for r in result if not r.get('draft')]
    else:return [{'version':app['version']}]
    versions=sorted({v for v in versions if isinstance(v,str) and VERSION.fullmatch(v)},key=lambda x:tuple(int(n) for n in re.findall(r'\d+',x)),reverse=True)
    return [{'version':v,'latest':v==latest,'prerelease':prerelease(v) or tool in NPM and '-' in v.split('+',1)[0]} for v in versions[:50]]


def replace_version(value,old,new):
    return value.replace(old.lstrip('vn'),new.lstrip('vn'))


def candidate(base,version,arch):
    if not VERSION.fullmatch(version):raise ValueError('Versione non valida')
    app=copy.deepcopy(base);tool=app['id'];old=app['version'];app['version']=version
    for field,value in app.get('install',{}).items():
        if isinstance(value,str):app['install'][field]=replace_version(value,old,version)
    kind=app.get('install',{}).get('kind')
    if tool=='verapdf':
        family='.'.join(version.split('.')[:2])
        name='verapdf-greenfield-'+version+'-installer.zip'
        url='https://software.verapdf.org/releases/'+family+'/'+name
        sha,size=sha_asset(url)
        app['assets']={arch:{'name':name,'url':url,'sha256':sha,'size_bytes':size}}
        return {'app':app,'requested':version,'arch':arch,'resolve_dependencies':False}
    if tool in PYPI or kind=='debian' or tool=='structurizr':
        return {'app':app,'requested':version,'arch':arch,'resolve_dependencies':True}
    if tool in NPM:
        metadata=data('https://registry.npmjs.org/'+urllib.parse.quote(NPM[tool],safe='@/')+'/'+urllib.parse.quote(version,safe=''))
        app['version']=metadata['version']
        asset=metadata['dist'];url=asset['tarball']
        if not url.startswith('https://registry.npmjs.org/'):raise ValueError('Origine NPM non valida')
        sha,size=sha_asset(url)
        app['assets']={arch:{'name':url.rsplit('/',1)[1],'url':url,'sha256':sha,'size_bytes':size or 0}}
        return {'app':app,'requested':version,'arch':arch,'resolve_dependencies':True,'npm_package':NPM[tool]}
    repo=gh_repository(app);release=None
    if repo and tool not in ('ffmpeg','calibre','blender'):
        try:release=data('https://api.github.com/repos/'+repo+'/releases/tags/'+urllib.parse.quote(version,safe=''))
        except urllib.error.HTTPError as error:
            if error.code!=404:raise
            release=data('https://api.github.com/repos/'+repo+'/releases/tags/'+urllib.parse.quote('v'+version.lstrip('v'),safe=''))
        app['version']=release['tag_name']
    assets={}
    for architecture,asset in base['assets'].items():
        if architecture!=arch:continue
        selected=None
        name=replace_version(asset['name'],old,version)
        if release:
            selected=next((a for a in release.get('assets',[]) if a['name']==name),None)
            if selected is None and kind in ('freecad-appimage','musescore-appimage'):
                pattern=r'(?:x86_64|amd64)' if arch=='amd64' else r'(?:aarch64|arm64)'
                compatible=[a for a in release.get('assets',[]) if a['name'].endswith('.AppImage') and re.search(pattern,a['name'],re.I)]
                if len(compatible)==1:selected=compatible[0]
            if selected:name=selected['name']
            if not selected and not ('codeload.github.com' in asset['url']):continue
        url=selected['browser_download_url'] if selected else replace_version(asset['url'],old,version)
        if tool=='blender':
            previous='.'.join(old.split('.')[:2]);current='.'.join(version.lstrip('v').split('.')[:2])
            url=url.replace('Blender'+previous,'Blender'+current)
        if release and selected and not url.startswith('https://github.com/'+repo+'/releases/download/'):
            raise ValueError('Distribuzione estranea al repository ufficiale')
        sha,size=sha_asset(url,selected.get('digest') if selected else None)
        original={k:v for k,v in asset.items() if k!='sha512'}
        if kind=='upstream-deb':original['package_version']=app['version'].lstrip('v')
        if 'version' in original:original['version']=app['version']
        assets[architecture]={**original,'name':name,'url':url,'sha256':sha,'size_bytes':size if size is not None else selected.get('size',0)}
    if arch not in assets:raise ValueError('Questa release non fornisce una distribuzione supportata per '+arch)
    app['assets']=assets
    return {'app':app,'requested':version,'arch':arch,'resolve_dependencies':False}


def latest(app):
    tool=app['id'];repo=gh_repository(app)
    if tool in NPM:
        value=data('https://registry.npmjs.org/'+urllib.parse.quote(NPM[tool],safe='@/')+'/latest')['version']
        if not prerelease(value) and '-' not in value.split('+',1)[0]:return value
    if app.get('install',{}).get('kind')=='debian':return 'latest'
    if repo and tool not in NPM and tool not in PYPI and tool not in ('ffmpeg','calibre','blender','verapdf'):
        value=data('https://api.github.com/repos/'+repo+'/releases/latest')
        if value.get('draft') or value.get('prerelease') or prerelease(value.get('tag_name','')):raise ValueError('Il registro non indica una release stabile')
        return value['tag_name']
    if tool=='calibre':
        value=read('https://code.calibre-ebook.com/latest-stable',4096).decode().strip()
        if not VERSION.fullmatch(value):raise ValueError('Versione Calibre non riconosciuta')
        return value
    values=options(app)
    stable=[v for v in values if not v.get('prerelease')]
    if not stable:raise ValueError('Nessuna release stabile disponibile')
    return next((v['version'] for v in stable if v.get('latest')),stable[0]['version'])
