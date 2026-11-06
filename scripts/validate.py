#!/usr/bin/env python3
"""Validate catalog, schemas and Compose wiring without provider requests."""
import ast
import json
from pathlib import Path
import re
import runpy
import yaml

ROOT = Path(__file__).resolve().parents[1]

def main():
    lock=json.loads((ROOT/'versions.lock.json').read_text())
    cfg=yaml.safe_load((ROOT/'config/righaven.yaml').read_text())
    local=yaml.safe_load((ROOT/'docker-compose.yaml').read_text())
    remote=yaml.safe_load((ROOT/'config/compose.hostinger.template.yaml').read_text())
    agy=json.loads((ROOT/'scripts/antigravity.lock.json').read_text())
    assert lock['cli_runtimes']['antigravity']==lock['cli_runtimes']['gemini']==agy['version']
    assert all(p['version']==agy['version'] for p in agy['platforms'].values())
    npm=json.loads((ROOT/'config/toolkit/package-lock.json').read_text())
    browser=next(a['version'] for a in lock['applications'] if a['id']=='playwright')
    assert npm['packages']['']['dependencies']['@playwright/test']==browser
    assert npm['packages']['node_modules/@playwright/test']['version']==browser
    diagram_packages={'mermaid':'@mermaid-js/mermaid-cli','excalidraw':'@excalidraw/excalidraw','bpmn':'bpmn-to-image'}
    versions={a['id']:a['version'].removeprefix('v') for a in lock['applications']}
    for identifier,package in diagram_packages.items():
        package_lock=json.loads((ROOT/'config/toolkit/design'/identifier/'package-lock.json').read_text())
        assert package_lock['packages']['']['dependencies'][package]==versions[identifier]
        assert package_lock['packages']['node_modules/'+package]['version']==versions[identifier]
        assert package_lock['packages']['']['dependencies']['playwright-core']==browser
    java=json.loads((ROOT/'config/toolkit/design/structurizr/libraries.json').read_text())
    for asset in [java['runtime'],*java['libraries']]:
        assert Path(asset['name']).name==asset['name'] and re.fullmatch('[a-f0-9]{64}',asset['sha256']) and asset['size_bytes']>0
        assert asset['url'].startswith(('https://repo.maven.apache.org/maven2/','https://github.com/adoptium/temurin21-binaries/releases/download/'))
    assert any(a['name']=='structurizr-dsl-'+versions['structurizr']+'.jar' for a in java['libraries'])
    ids={a['id'] for a in lock['applications']}
    assert len(ids)==len(lock['applications']) and ids==set(cfg['subagents']['custom_agents'])
    # Recipes are skills that orchestrate several catalog tools end to end.
    recipe_catalog=json.loads((ROOT/'righaven/recipes.json').read_text())['recipes']
    recipes={r['skill'] for r in recipe_catalog}
    assert all(set(r['tools'])<=ids for r in recipe_catalog), 'Ricetta con strumenti fuori catalogo'
    expected_skills={'skill-'+identifier for identifier in ids}|{'skill-workspace','skill-harness','skill-problem-solving','skill-quality-review'}|recipes
    assert {p.parent.name for p in (ROOT/'skills/custom').glob('*/SKILL.md')}==expected_skills
    assert ids == set(runpy.run_path(str(ROOT/'scripts/acceptance.py'))['CASES'])
    assert (ROOT/'righaven/righaven.yaml').read_bytes()==(ROOT/'config/righaven.yaml').read_bytes()
    assert (ROOT/'righaven/versions.lock.json').read_bytes()==(ROOT/'versions.lock.json').read_bytes()
    for a in lock['applications']:
        for resource in a.get('resources', []):
            assert re.fullmatch('[a-f0-9]{64}', resource['sha256']) and resource['size_bytes'] > 0
            assert resource.get('license') and resource.get('source')
            assert resource['url'].startswith(('https://deb.debian.org/debian/pool/', 'https://huggingface.co/ggerganov/whisper.cpp/resolve/'))
            if resource.get('kind') == 'file':
                assert re.fullmatch('[a-f0-9]{40}', resource['revision']) and resource['revision'] in resource['url']
                assert '..' not in Path(resource['install_path']).parts and not Path(resource['install_path']).is_absolute()
        if a.get('install', {}).get('kind') == 'debian':
            assert all(v.get('package') and v.get('package_version') for v in a['assets'].values())
        for asset in a['assets'].values():
            assert re.fullmatch('[a-f0-9]{64}',asset['sha256'])
            assert asset['url'].startswith(a.get('download_base', a['repository']+'/releases/download/'+a['version']+'/'))
        skill=ROOT/'skills/custom'/('skill-'+a['id'])/'SKILL.md'
        assert skill.is_file()
        assert (skill.parent/'references/CLI-RECIPE.md').is_file()
        assert (skill.parent/'references/CAPABILITIES.md').is_file(), f'Mappa capacità mancante: {skill}'
        assert (skill.parent/'references/QUALITY.md').is_file(), f'Criteri professionali mancanti: {skill}'
        assert any(h in skill.read_text() for h in ('## Consegna: sorgenti modificabili e compatibilità','## Delivery: editable sources and compatibility')), f'Contratto sorgenti mancante: {skill}'
        assert 'delivery' in (skill.parent/'references/CLI-RECIPE.md').read_text()
        front=yaml.safe_load(skill.read_text().split('---',2)[1])
        assert front['name']==skill.parent.name and front['description']
        for path in [skill, skill.parent/'references/CLI-RECIPE.md']:
            assert '/opt/righaven/bin/' not in path.read_text(), f'Percorso CLI inesistente: {path}'
    assert cfg['database']['sqlite_dir']=='/righaven-state/database', 'Managed SQLite must live on the persistent state volume'
    assert cfg['sandbox']['allow_host_bash'] is False
    assert cfg['subagent_runtime']['max_running']==1
    assert any(t['name']=='harness_delegate' for t in cfg['tools'])
    assert cfg['models'][0]['use']=='righaven.codex_provider:HarnessCodexChatModel'
    assert not any(t['name'] in ('bash', 'write_file', 'str_replace') for t in cfg['tools'])
    for compose in [local,remote]:
        assert 'righaven-state:/righaven-state' in compose['services']['gateway']['volumes']
        assert compose['services']['gateway']['environment']['RIGHAVEN_DOCKER_SCOPE']=='internal'
        assert compose['services']['gateway']['environment']['DOCKER_HOST']=='unix:///runtime/docker.sock'
        assert compose['services']['runtime-docker']['privileged'] is True
        assert compose['services']['runtime-docker']['command']==['dockerd','--host=unix:///runtime/docker.sock']
        assert any('runtime-docker-data:/var/lib/docker' in str(v) for v in compose['services']['runtime-docker']['volumes'])
        assert any('runtime-docker-control:/runtime' in str(v) for v in compose['services']['runtime-docker']['volumes'])
        assert not any('2375' in str(value) or '2376' in str(value) for value in compose['services']['runtime-docker'].values())
        assert not any('docker.sock' in str(v) for service in compose['services'].values() for v in service.get('volumes',[]))
        assert not any('.env' in str(s.get('env_file','')) for s in compose['services'].values())
    for name in ['gateway','frontend']:
        assert not local['services'][name]['build'].get('additional_contexts')
        assert 'COPY core/' in (ROOT/'docker'/('Dockerfile.'+name)).read_text()
    assert lock['righaven_core']['ownership']=='in-repository'
    custom={'gateway','frontend'}
    assert 'proxy' not in remote['services']
    assert all('build' not in remote['services'][name] for name in custom)
    assert all(remote['services'][name]['image'].startswith('ghcr.io/ggmm82/righaven-') for name in custom)
    assert all(':sha-' in remote['services'][name]['image'] for name in custom)
    assert 'networks' not in remote
    assert not any('traefik.docker.network=' in label for name in ['gateway','frontend'] for label in remote['services'][name]['labels'])
    assert not any('ports' in remote['services'][name] for name in remote['services'])
    gateway_labels='\n'.join(remote['services']['gateway']['labels'])
    assert 'PathPrefix(`/api/langgraph/`)' in gateway_labels
    assert 'replacepathregex.regex=^/api/langgraph/(.*)' in gateway_labels
    assert 'replacepathregex.replacement=/api/$${1}' in gateway_labels
    caddy=(ROOT/'docker/Caddyfile').read_text()
    assert 'handle /api/langgraph/*' in caddy and 'uri replace /api/langgraph /api' in caddy
    for folder in ['scripts','righaven','tests']:
        for path in (ROOT/folder).glob('*.py'):ast.parse(path.read_text(),str(path))
    print(f'OK: {len(ids)} specialisti, {len(expected_skills)} skills, checksum, budget condiviso, Compose locale/remoto e assenza socket nei worker.')

if __name__=='__main__':main()
