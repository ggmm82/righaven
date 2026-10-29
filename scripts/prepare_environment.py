"""Trusted preparation recipe: only locked tools, no accounts or project mounts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path('/opt/righaven')

VERIFICATION_DEPENDENCIES = {
        'designcraft':{'pdfcraft'}, 'wordcraft':{'pdfcraft'}, 'pdfcraft':{'wordcraft'}, 'typst':{'pdfcraft'}, 'epubcheck':{'pandoc'},
        'soundcraft':{'ffmpeg'}, 'filmcraft':{'ffmpeg'}, 'effectcraft':{'ffmpeg'},
        'fluidsynth':{'ffmpeg'}, 'whisper':{'ffmpeg'}, 'musescore':{'ffmpeg'},
        'manim':{'ffmpeg'}, 'opentimelineio':{'ffmpeg'}, 'calibre':{'pdfcraft'}}


def step(label,**fields):
    print(json.dumps({'phase':label,'at':time.time(),**fields}),flush=True)


def installed_versions():
    installed=json.loads((ROOT/'installed.json').read_text())
    result={row['id']:row['version'] for row in installed}
    lock=json.loads((ROOT/'catalog.lock.json').read_text())
    result.update({'provider-'+('agy' if key=='gemini' else key):value for key,value in lock.get('cli_runtimes',{}).items() if key in ('codex','claude')})
    agy=ROOT/'antigravity.lock.json'
    if agy.is_file():result['provider-agy']=json.loads(agy.read_text())['version']
    return result


def verify_native(tools):
    step('checking')
    subprocess.run([sys.executable,str(ROOT/'smoke.py'),'--mcp','--output','/tmp/environment-smoke.json'],check=True)
    subprocess.run([sys.executable,str(ROOT/'check_tool_capabilities.py'),'--native'],check=True)
    tested = [t for t in tools if VERIFICATION_DEPENDENCIES.get(t,set()).issubset(tools)]
    if tested:
        subprocess.run([sys.executable,str(ROOT/'acceptance.py'),'--agents',*tested,'--output','/mnt/user-data/outputs/environment-checks/report.json'],check=True)
    return tested


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    if spec.get('reset_providers'):
        from apply_tool_versions import reset_providers
        reset_providers(spec['reset_providers'])
    version_packages=spec.get('version_packages',{})
    if version_packages:
        from apply_tool_versions import apply,verify
        if spec.get('verify_only') is True:verify(version_packages)
        else:apply(version_packages)
    lock = json.loads((ROOT/'catalog.lock.json').read_text())
    known = {a['id']:a for a in lock['applications']}
    tools = spec.get('tools')
    if not isinstance(tools,list) or (not tools and not version_packages) or len(tools)>64 or any(t not in known for t in tools):
        raise ValueError('Selezione strumenti non valida')
    tools = sorted(set(tools))
    if spec.get('verify_only') is True:
        installed = json.loads((ROOT/'installed.json').read_text())
        if {row['id'] for row in installed} != set(tools):
            raise ValueError('Il contenuto dell’immagine non corrisponde al manifest')
        actual = json.loads((ROOT/'versions.lock.json').read_text())
        if actual != {**lock, 'applications':[a for a in lock['applications'] if a['id'] in tools]}:
            raise ValueError('Versioni dei programmi diverse dal catalogo locale')
        if tools:verify_native(tools)
        shutil.rmtree('/mnt/user-data',ignore_errors=True)
        Path('/mnt/user-data').mkdir(parents=True,exist_ok=True)
        step('verified',installed_versions=installed_versions())
        return
    inherited=json.loads((ROOT/'installed.json').read_text())
    reused={row['id'] for row in inherited}
    if reused-set(tools):raise ValueError('Base environment contains tools outside the requested recipe')
    missing=set(tools)-reused
    free = shutil.disk_usage('/').free
    estimate = max(512*1024**2, sum(max((v.get('size_bytes',0) for v in known[t]['assets'].values()), default=0) for t in missing)*3)
    if free < estimate + 512*1024**2:
        raise ValueError('Spazio insufficiente per preparare gli strumenti richiesti')
    step('installing')
    if tools:subprocess.run([sys.executable,str(ROOT/'install_environment_tools.py'),'--apps',*tools],check=True)
    step('adapters')
    for app in sorted(missing):
        if known[app].get('install',{}).get('kind')=='design-node':
            subprocess.run(['node',str(ROOT/'build_design_web.cjs'),app,str(ROOT/'apps'/app),str(ROOT/'apps'/app/'web')],check=True)
    if 'structurizr' in missing:
        classes=ROOT/'apps/structurizr/classes';classes.mkdir(exist_ok=True)
        subprocess.run([str(ROOT/'apps/structurizr/jdk/bin/javac'),'-cp',str(ROOT/'apps/structurizr/jars/*'),'-d',str(classes),str(ROOT/'StructurizrJob.java')],check=True)
    for name in ('ffmpeg','ffprobe'):
        if 'ffmpeg' in tools and not Path('/usr/bin',name).exists():
            Path('/usr/bin',name).symlink_to('/usr/local/bin/'+name)
    subprocess.run(['fc-cache','-f'],check=True)
    # The runtime manifest describes what is actually installed, not the whole catalogue.
    lock['applications']=[a for a in lock['applications'] if a['id'] in tools]
    (ROOT/'versions.lock.json').write_text(json.dumps(lock))
    capabilities=json.loads((ROOT/'catalog-capabilities.json').read_text())
    if version_packages:
        from apply_tool_versions import refresh_capabilities
        refresh_capabilities(capabilities,version_packages)
        (ROOT/'catalog-capabilities.json').write_text(json.dumps(capabilities))
    capabilities['applications']=[a for a in capabilities['applications'] if a['id'] in tools]
    (ROOT/'tool-capabilities.json').write_text(json.dumps(capabilities))
    from apply_tool_versions import check_providers
    check_providers(version_packages)
    tested = verify_native(tools) if tools else []
    (ROOT/'environment.json').write_text(json.dumps({'tools':tools,'verified':True,'recipe':1,
        'version_packages':version_packages,'versions':spec.get('versions',{}),'reused_tools':sorted(reused),'installed_tools':sorted(missing),
        'checks':{'registries':'passed','native_workflows':tested,'workflows_not_run':sorted(set(tools)-set(tested))}}))
    shutil.rmtree('/mnt/user-data',ignore_errors=True)
    Path('/mnt/user-data').mkdir(parents=True,exist_ok=True)
    step('verified',installed_versions=installed_versions())


if __name__=='__main__':
    main()
