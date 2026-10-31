"""Trusted native dependency resolver. No models, credentials or project mounts."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT=Path('/opt/righaven')
NPM={'playwright':'@playwright/test','mermaid':'@mermaid-js/mermaid-cli','excalidraw':'@excalidraw/excalidraw','bpmn':'bpmn-to-image','provider-codex':'@openai/codex','axe-core':'@axe-core/playwright','spectral':'@stoplight/spectral-cli','ajv':'ajv-cli','mjml':'mjml'}
PYPI={'dlt':'dlt','sqlmesh':'sqlmesh','sqlglot':'sqlglot','ifcopenshell':'ifcopenshell','manim':'manim','opentimelineio':'opentimelineio','pymeshlab':'pymeshlab','schemathesis':'schemathesis'}


def fetch(url,path):
    sha=hashlib.sha256()
    with urllib.request.urlopen(url,timeout=120) as source,path.open('wb') as target:
        while chunk:=source.read(1024**2):target.write(chunk);sha.update(chunk)
    return sha.hexdigest()


def resolve(spec):
    app=spec['app'];tool=app['id'];arch=spec['arch'];version=spec['requested'];files={}
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.+:~_-]{0,100}',version):raise ValueError('Versione non valida')
    if not spec.get('resolve_dependencies'):return {'app':app,'files':files}
    if tool in NPM:
        relative='provider-clis/codex' if tool=='provider-codex' else 'toolkit-lock' if tool=='playwright' else 'toolkit-lock/extended/'+tool if tool in ('axe-core','spectral','ajv','mjml') else 'toolkit-lock/design/'+tool
        template=ROOT/relative/'package.json'
        package=json.loads(template.read_text()) if template.is_file() else {'name':'skill-provider-codex','version':'1.0.0','private':True,'dependencies':{}}
        package.setdefault('dependencies',{})[NPM[tool]]=version
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'package.json').write_text(json.dumps(package))
            subprocess.run(['npm','install','--package-lock-only','--ignore-scripts','--no-audit','--no-fund','--prefix',directory],check=True,timeout=600)
            lock=json.loads((folder/'package-lock.json').read_text())
            for dependency in lock.get('packages',{}).values():
                url=dependency.get('resolved','')
                if url and not url.startswith('https://registry.npmjs.org/'):raise ValueError('Dipendenza NPM non ufficiale o locale')
            files[relative+'/package.json']=json.dumps(package)
            files[relative+'/package-lock.json']=json.dumps(lock)
    elif tool in PYPI:
        from install_system_packages import install
        install(ROOT,[tool])
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);venv=folder/'venv';subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
            report=folder/'report.json'
            requirements=[PYPI[tool]+'=='+version]
            if tool=='dlt':requirements=['dlt[duckdb,sql_database]=='+version,'sqlglot','psycopg[binary]','pymysql','pymongo','pymssql']
            subprocess.run([str(venv/'bin/python'),'-m','pip','install','--dry-run','--ignore-installed','--report',str(report),*requirements],check=True,timeout=1200)
            rows=json.loads(report.read_text())['install'];lines=[]
            for row in rows:
                name=row['metadata']['name'];resolved=row['metadata']['version'];info=row['download_info'];url=info['url']
                if not url.startswith('https://files.pythonhosted.org/'):raise ValueError('Dipendenza Python non ufficiale')
                sha=info['archive_info'].get('hashes',{}).get('sha256')
                if not sha or not re.fullmatch(r'[a-f0-9]{64}',sha):raise ValueError('Dipendenza senza checksum')
                lines.append(name+'=='+resolved+' --hash=sha256:'+sha)
                if name.lower().replace('-','').replace('_','')==PYPI[tool].replace('-','').replace('_',''):
                    metadata=json.load(urllib.request.urlopen('https://pypi.org/pypi/'+PYPI[tool]+'/'+resolved+'/json',timeout=60))
                    artifact=next(item for item in metadata['urls'] if item['url']==url and item['digests']['sha256']==sha)
                    app['version']=resolved;app['assets']={arch:{'name':url.rsplit('/',1)[1],'url':url,'sha256':sha,'size_bytes':artifact['size']}}
            files['toolkit-lock/python/'+tool+'.txt']='\n'.join(lines)+'\n'
    elif app.get('install',{}).get('kind')=='debian':
        from install_extended import repository
        from install_righaven import download
        repository(app,ROOT,download)
        package=next(iter(app['assets'].values()))['package']
        subprocess.run(['apt-get','update'],check=True)
        if version=='latest':
            policy=subprocess.check_output(['apt-cache','policy',package],text=True)
            match=re.search(r'Candidate: (\S+)',policy)
            if not match or match[1]=='(none)':raise ValueError('Nessuna versione stabile compatibile con questa base Debian')
            version=match[1];app['version']=version
        metadata=subprocess.check_output(['apt-cache','show',package+'='+version],text=True)
        fields=dict(line.split(': ',1) for line in metadata.split('\n\n')[0].splitlines() if ': ' in line and not line.startswith(' '))
        uris=subprocess.check_output(['apt-get','--print-uris','download',package+'='+version],text=True)
        match=re.search(r"^'([^']+)'",uris,re.M)
        if not match:raise ValueError('APT did not identify an official package distribution')
        source=match[1].replace('http://','https://',1)
        allowed=('https://deb.debian.org/debian/','https://deb.debian.org/debian-security/',
                 'https://build.openmodelica.org/apt/')
        if not source.startswith(allowed):raise ValueError('Package distribution is outside reviewed repositories')
        app['assets']={arch:{'name':Path(fields['Filename']).name,'url':source,'sha256':fields['SHA256'],'size_bytes':int(fields['Size']),'package':package,'package_version':fields['Version']}}
    elif tool=='structurizr':
        subprocess.run(['apt-get','update'],check=True);subprocess.run(['apt-get','install','-y','--no-install-recommends','maven'],check=True)
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);jars=folder/'jars';repo=folder/'m2'
            pom='<project><modelVersion>4.0.0</modelVersion><groupId>righaven</groupId><artifactId>resolver</artifactId><version>1</version><dependencies><dependency><groupId>com.structurizr</groupId><artifactId>structurizr-dsl</artifactId><version>'+version+'</version></dependency></dependencies></project>'
            (folder/'pom.xml').write_text(pom)
            subprocess.run(['mvn','-B','-q','-f',str(folder/'pom.xml'),'-Dmaven.repo.local='+str(repo),'org.apache.maven.plugins:maven-dependency-plugin:3.8.1:copy-dependencies','-DincludeScope=runtime','-DoutputDirectory='+str(jars)],check=True,timeout=900)
            metadata=json.loads((ROOT/'toolkit-lock/design/structurizr/libraries.json').read_text());libraries=[]
            for jar in sorted(jars.glob('*.jar')):
                original=next(repo.rglob(jar.name));relative=original.relative_to(repo)
                url='https://repo.maven.apache.org/maven2/'+str(relative)
                asset={'name':jar.name,'url':url,'sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'size_bytes':jar.stat().st_size}
                libraries.append(asset)
                if jar.name=='structurizr-dsl-'+version+'.jar':app['assets']={arch:asset}
            metadata['libraries']=libraries;files['toolkit-lock/design/structurizr/libraries.json']=json.dumps(metadata)
    return {'app':app,'files':files}


if __name__=='__main__':
    value=resolve(json.loads(Path(sys.argv[1]).read_text()))
    Path(sys.argv[2]).write_text(json.dumps(value))
