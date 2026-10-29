"""Apply an immutable, Gateway-resolved version plan inside preparation only."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT=Path('/opt/righaven')
BIN=Path('/usr/local/bin')


def reset_providers(defaults):
    """Reset only overridden CLIs, retaining the inherited application layers."""
    for tool,app in defaults.items():
        if tool!=app.get('id') or tool not in ('provider-agy','provider-codex','provider-claude'):
            raise ValueError('Ripristino CLI non valido')
        if tool in ('provider-agy','provider-claude'):
            apply({tool:{'app':app,'files':{}}})
        else:
            # Custom Codex installs live under provider-clis, so npm's original
            # global installation from the immutable core remains intact.
            directory=Path(subprocess.check_output(['npm','root','-g'],text=True).strip())
            binary=directory/'@openai/codex/bin/codex.js'
            if not binary.is_file():raise ValueError('CLI Codex originale non disponibile nella base')
            link=BIN/'codex'
            if link.exists() or link.is_symlink():link.unlink()
            link.symlink_to(binary)
            actual=subprocess.check_output(['codex','--version'],text=True,stderr=subprocess.STDOUT,timeout=90)
            if app['version'].lstrip('v') not in actual:raise ValueError('Versione Codex originale diversa dalla richiesta')
            catalog=json.loads((ROOT/'catalog.lock.json').read_text())
            catalog['cli_runtimes']['codex']=app['version']
            (ROOT/'catalog.lock.json').write_text(json.dumps(catalog))


def apply(packages):
    catalog=json.loads((ROOT/'catalog.lock.json').read_text())
    indexed={a['id']:a for a in catalog['applications']}
    for tool,bundle in packages.items():
        app=bundle['app']
        if tool!=app['id']:raise ValueError('Versione di un altro strumento')
        for name,content in bundle.get('files',{}).items():
            path=ROOT/name
            if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(ROOT):raise ValueError('Dipendenza fuori dal programma')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        if tool.startswith('provider-'):
            provider=tool.removeprefix('provider-');destination=ROOT/'provider-clis'/provider
            destination.mkdir(parents=True,exist_ok=True)
            if provider=='codex':
                subprocess.run(['npm','ci','--prefix',str(destination),'--ignore-scripts','--no-audit','--no-fund'],check=True)
                binary=destination/'node_modules/.bin/codex'
                catalog['cli_runtimes']['codex']=app['version']
            elif provider in ('agy','claude'):
                import platform
                arch={'x86_64':'amd64','aarch64':'arm64'}[platform.machine()]
                asset=app['assets'][arch]
                with tempfile.TemporaryDirectory() as directory:
                    archive=Path(directory)/'cli.tar.gz'
                    with urllib.request.urlopen(asset['url'],timeout=120) as source,archive.open('wb') as target:shutil.copyfileobj(source,target)
                    if hashlib.sha256(archive.read_bytes()).hexdigest()!=asset['sha256']:raise ValueError('Distribuzione CLI modificata')
                    with tarfile.open(archive) as payload:
                        member=payload.getmember('package/claude' if provider=='claude' else 'antigravity')
                        if not member.isfile() or member.size>512*1024**2:raise ValueError('Eseguibile CLI non valido')
                        binary=destination/provider
                        with payload.extractfile(member) as source,binary.open('wb') as target:shutil.copyfileobj(source,target)
                        binary.chmod(0o755)
                lock={'version':app['version'],'source':app['repository']+'/releases/tag/'+app['version'],'platforms':app['assets']}
                if provider=='claude':catalog['cli_runtimes']['claude']=app['version']
                else:
                    catalog['cli_runtimes'].update(antigravity=app['version'],gemini=app['version'])
                    (ROOT/'antigravity.lock.json').write_text(json.dumps(lock))
            else:raise ValueError('Provider sconosciuto')
            link=BIN/provider
            if link.exists() or link.is_symlink():link.unlink()
            link.symlink_to(binary)
            actual=subprocess.check_output([provider,'--version'],text=True,stderr=subprocess.STDOUT,timeout=90)
            if app['version'].lstrip('v') not in actual:raise ValueError('Versione CLI diversa dalla richiesta')
        else:
            if tool not in indexed:raise ValueError('Strumento sconosciuto')
            indexed[tool]=app
    catalog['applications']=[indexed[a['id']] for a in catalog['applications']]
    (ROOT/'catalog.lock.json').write_text(json.dumps(catalog))
    return catalog


def refresh_capabilities(capabilities,packages):
    """Re-discover the installed registry; do not label old IDs as a new release."""
    try:from capability_catalog import command_ids
    except ImportError:from scripts.capability_catalog import command_ids
    from datetime import datetime,timezone
    for entry in capabilities['applications']:
        tool=entry['id']
        if tool not in packages:continue
        app=packages[tool]['app']
        text=subprocess.check_output([app['executable'],*app['registry_args']],text=True,timeout=60)
        ids=command_ids(text)
        if not ids:raise ValueError('Registro vuoto per la release selezionata: '+tool)
        registered=set(ids);groups=[];mapped=set()
        for group in entry['groups']:
            commands=[c for c in group['commands'] if c in registered]
            if commands:groups.append({**group,'commands':commands});mapped.update(commands)
        if registered-mapped:
            groups.append({'goal':'Operazioni rilevate: consulta gli schemi della CLI prima dell’uso',
                'commands':sorted(registered-mapped),'evidence':'registered'})
        entry.update(version=app['version'],catalog_ids=ids,catalog_count=len(ids),groups=groups,
            ids_sha256=hashlib.sha256(('\n'.join(ids)+'\n').encode()).hexdigest(),
            catalog_sha256=hashlib.sha256(text.encode()).hexdigest(),
            reference=app['repository']+' — registro della release '+app['version'],
            audited_at=datetime.now(timezone.utc).isoformat())
    return capabilities


def verify(packages):
    catalog=json.loads((ROOT/'catalog.lock.json').read_text())
    indexed={a['id']:a for a in catalog['applications']}
    for tool,bundle in packages.items():
        app=bundle['app']
        if not tool.startswith('provider-') and indexed.get(tool)!=app:raise ValueError('Catalogo diverso dalla versione richiesta')
        for name,content in bundle.get('files',{}).items():
            path=ROOT/name
            if not path.resolve().is_relative_to(ROOT) or path.read_text()!=content:raise ValueError('Dipendenze diverse dalla versione richiesta')
        if tool.startswith('provider-'):
            provider=tool.removeprefix('provider-')
            actual=subprocess.check_output([provider,'--version'],text=True,stderr=subprocess.STDOUT,timeout=90)
            if app['version'].lstrip('v') not in actual:raise ValueError('Versione CLI diversa dalla richiesta')
    check_providers(packages)


def check_providers(packages):
    if any(k.startswith('provider-') for k in packages):
        subprocess.run(['python3',str(ROOT/'check_provider_clis.py')],check=True)
