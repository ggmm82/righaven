#!/usr/bin/env python3
"""Build once, test the published digests, and promote identical verified trees."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

COMPONENTS = ('gateway', 'frontend', 'sandbox', 'proxy')
WORKFLOW = '.github/workflows/verify.yml'


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def api(repository, path):
    return json.loads(run('gh', 'api', f'repos/{repository}/{path}'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[a-f0-9]{40}', value))


def metadata():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    pr = event.get('pull_request')
    return {'version': 1, 'repository': os.environ['GITHUB_REPOSITORY'],
            'workflow': WORKFLOW, 'event': os.environ['GITHUB_EVENT_NAME'],
            'run_id': int(os.environ['GITHUB_RUN_ID']), 'run_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
            'source_commit': run('git', 'rev-parse', 'HEAD'),
            'tree': run('git', 'rev-parse', 'HEAD^{tree}'),
            'pull_request': event['number'] if pr else None,
            'head_sha': pr['head']['sha'] if pr else run('git', 'rev-parse', 'HEAD'),
            'head_repository': pr['head']['repo']['full_name'] if pr else os.environ['GITHUB_REPOSITORY']}


def validate_manifest(value, repository, tree=None, verified=False):
    if (not isinstance(value, dict) or value.get('version') != 1
            or value.get('repository') != repository or value.get('workflow') != WORKFLOW
            or value.get('head_repository') != repository
            or value.get('event') not in ('pull_request', 'push', 'workflow_dispatch')
            or any(not sha(value.get(k)) for k in ('source_commit', 'tree', 'head_sha'))
            or any(type(value.get(k)) is not int or value[k] < 1 for k in ('run_id', 'run_attempt'))):
        raise ValueError('Provenienza del manifest non valida')
    if value['event'] == 'pull_request' and (type(value.get('pull_request')) is not int or value['pull_request'] < 1):
        raise ValueError('Numero PR mancante')
    if tree is not None and value['tree'] != tree:
        raise ValueError('Il contenuto da rilasciare differisce da quello verificato')
    images = value.get('images', {})
    if not isinstance(images, dict) or set(images) != set(COMPONENTS):
        raise ValueError('Occorrono i quattro componenti della stessa verifica')
    for component, image in images.items():
        prefix = f'ghcr.io/{repository.lower()}-{component}@sha256:'
        if not isinstance(image, str) or not re.fullmatch(re.escape(prefix) + r'[a-f0-9]{64}', image):
            raise ValueError('Riferimento immutabile non valido: ' + component)
    if verified and value.get('verified') is not True:
        raise ValueError('Avvio completo non verificato')
    return value


def validate_bundle(directory, repository, tree=None):
    import yaml
    directory = Path(directory)
    value = validate_manifest(json.loads((directory / 'runtime-manifest.json').read_text()), repository, tree, verified=True)
    content = (directory / 'compose.hostinger.yaml').read_bytes()
    if hashlib.sha256(content).hexdigest() != value.get('compose_sha256'):
        raise ValueError('Compose diverso da quello verificato')
    try:
        compose = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise ValueError('Compose non valido') from error
    for service, component in (('gateway', 'gateway'), ('frontend', 'frontend')):
        if compose['services'][service]['image'] != value['images'][component]:
            raise ValueError('Il Compose non usa i digest del manifest')
    if compose['services']['gateway']['environment']['RIGHAVEN_SANDBOX_IMAGE'] != value['images']['sandbox']:
        raise ValueError('Immagine worker diversa dalla sandbox verificata')
    gateway = compose['services']['gateway']
    runtime = compose['services'].get('runtime-docker', {})
    if (gateway.get('environment', {}).get('RIGHAVEN_DOCKER_SCOPE') != 'internal'
            or gateway.get('environment', {}).get('DOCKER_HOST') != 'unix:///runtime/docker.sock'
            or runtime.get('privileged') is not True
            or runtime.get('command') != ['dockerd', '--host=unix:///runtime/docker.sock']
            or not any('runtime-docker-data:/var/lib/docker' in str(item) for item in runtime.get('volumes', []))
            or not any('runtime-docker-control:/runtime' in str(item) for item in runtime.get('volumes', []))
            or any('docker.sock' in str(item) for service in compose.get('services', {}).values()
                   for item in service.get('volumes', []))):
        raise ValueError('Il Compose non usa il runtime RigHaven interno persistente')
    return value


def assemble(directory, expected):
    images = {}
    for component in COMPONENTS:
        item = json.loads((Path(directory) / f'{component}.json').read_text())
        recorded = item.get('metadata', {})
        core = {k: v for k, v in recorded.items() if k != 'run_attempt'}
        expected_core = {k: v for k, v in expected.items() if k != 'run_attempt'}
        if (core != expected_core or item.get('component') != component
                or type(recorded.get('run_attempt')) is not int
                or not 1 <= recorded['run_attempt'] <= expected['run_attempt']):
            raise ValueError('Ricevute provenienti da verifiche diverse')
        images[component] = item['image']
    return validate_manifest({**expected, 'images': images}, expected['repository'], expected['tree'])


def reusable(value, repository, tree, pr, workflow_run):
    try:
        validate_manifest(value, repository, tree, verified=True)
        return (workflow_run['conclusion'] == 'success' and workflow_run['event'] == 'pull_request'
                and workflow_run['head_repository']['full_name'] == repository
                and workflow_run['head_sha'] == pr['head']['sha']
                and workflow_run['path'].split('@')[0] == WORKFLOW
                and value['event'] == 'pull_request' and value['pull_request'] == pr['number']
                and value['head_sha'] == pr['head']['sha']
                and value['run_id'] == workflow_run['id']
                and value['run_attempt'] <= workflow_run['run_attempt']
                and pr['merged_at'] is not None and pr['base']['ref'] == 'main'
                and pr['base']['repo']['full_name'] == repository
                and pr['head']['repo']['full_name'] == repository)
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def resolve(repository, commit, directory, github=api, download=None):
    """No matching successful PR artifact means build current main, never guess."""
    tree = run('git', 'rev-parse', commit + '^{tree}')
    prs = github(repository, f'commits/{commit}/pulls?per_page=100')
    prs = [p for p in prs if p.get('merge_commit_sha') == commit and p.get('merged_at')]
    if not prs:
        return False
    runs = github(repository, 'actions/workflows/verify.yml/runs?event=pull_request&status=completed&per_page=100')['workflow_runs']
    for pr in prs:
        for candidate in runs:
            if candidate.get('conclusion') != 'success' or candidate.get('head_sha') != pr['head']['sha']:
                continue
            try:
                with tempfile.TemporaryDirectory() as temp:
                    if download:
                        download(candidate['id'], temp)
                    else:
                        run('gh', 'run', 'download', str(candidate['id']), '--repo', repository,
                            '--name', 'verified-runtime', '--dir', temp)
                    value = validate_bundle(temp, repository, tree)
                    if not reusable(value, repository, tree, pr, candidate):
                        continue
                    for filename in ('runtime-manifest.json', 'compose.hostinger.yaml'):
                        target = Path(directory) / filename
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes((Path(temp) / filename).read_bytes())
                    return True
            except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
                continue
    return False


def publish(directory, repository, commit, main):
    value = validate_bundle(directory, repository, run('git', 'rev-parse', 'HEAD^{tree}'))
    if main:
        # A slower old run must not replace the release of a newer main commit.
        if api(repository, 'git/ref/heads/main')['object']['sha'] != commit:
            raise ValueError('main è avanzato: il rilascio più recente resta invariato')
        tag, target = 'harness-' + commit, commit
        title = 'RigHaven ' + commit[:8]
    else:
        tag = f"pr-{value['pull_request']}-run-{value['run_id']}-{value['run_attempt']}" if value['pull_request'] else f"test-run-{value['run_id']}-{value['run_attempt']}"
        target = value['head_sha']
        title = f"Prova PR #{value['pull_request']} · {value['head_sha'][:8]}" if value['pull_request'] else 'Prova manuale RigHaven'
        if value['event'] == 'pull_request':
            pr = api(repository, 'pulls/' + str(value['pull_request']))
            if pr['head']['sha'] != value['head_sha']:
                raise ValueError('La PR è cambiata: usare il Compose della nuova verifica')
    url = f'https://github.com/{repository}/releases/download/{tag}/compose.hostinger.yaml'
    notes = Path(directory) / 'notes.md'
    notes.write_text(f'''{title}

Immagini identiche a quelle verificate: quattro componenti per digest immutabile.
Verifica: https://github.com/{repository}/actions/runs/{value['run_id']}
Contenuto Git verificato: `{value['tree']}`.

[Scarica il Compose Hostinger]({url}). Conservare progetto, variabili e volumi.
Il rilascio non installa automaticamente sul VPS. Per il collaudo prima del merge
usare un progetto di prova separato, con account e dati di prova; non condividere
volumi o credenziali della produzione.
''')
    existing = subprocess.run(['gh', 'release', 'view', tag, '--repo', repository], capture_output=True).returncode == 0
    assets = [str(Path(directory) / f) for f in ('compose.hostinger.yaml', 'runtime-manifest.json')]
    if not existing:
        args = ['gh', 'release', 'create', tag, '--repo', repository, '--target', target,
                '--title', title, '--notes-file', str(notes), '--draft', '--latest=false']
        if not main:
            args += ['--prerelease']
        # Upload while draft: latest must never point at a release without its Compose.
        run(*args, *assets)
        draft = True
    else:
        info = json.loads(run('gh', 'release', 'view', tag, '--repo', repository,
                              '--json', 'isDraft,targetCommitish'))
        draft = info['isDraft']
        if draft:
            if info['targetCommitish'] != target:
                raise ValueError('Bozza riferita a un commit diverso')
            run('gh', 'release', 'upload', tag, '--repo', repository, '--clobber', *assets)
        else:
            with tempfile.TemporaryDirectory() as temp:
                run('gh', 'release', 'download', tag, '--repo', repository, '--dir', temp)
                previous = validate_bundle(temp, repository, value['tree'])
                if any(previous[k] != value[k] for k in ('images', 'compose_sha256')):
                    raise ValueError('Il rilascio esiste già con runtime diversi: non sovrascriverlo')
    if draft:
        if main and api(repository, 'git/ref/heads/main')['object']['sha'] != commit:
            raise ValueError('main è avanzato: la bozza non diventa stabile')
        run('gh', 'release', 'edit', tag, '--repo', repository, '--draft=false',
            '--latest=true' if main else '--latest=false')
    summary = f'## Compose pronto\n\n[Scarica il Compose {"stabile" if main else "di prova PR"}]({url})\n\n'
    summary += 'Immagini pubblicate dopo i controlli; il manifest indica il run che le ha verificate.\n' if main else 'Installa in un progetto di prova, collauda e poi esegui il merge.\n'
    summary += f"\nDigest verificati nella [CI](https://github.com/{repository}/actions/runs/{value['run_id']}).\n"
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(summary)
    print(url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['resolve', 'record', 'assemble', 'pull', 'seal', 'publish'])
    parser.add_argument('--directory', type=Path, default=Path('reports/verified-runtime'))
    parser.add_argument('--component', choices=COMPONENTS)
    parser.add_argument('--image')
    args = parser.parse_args()
    repository, commit = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA']
    if args.action == 'resolve':
        reuse = False
        if os.environ['GITHUB_EVENT_NAME'] == 'push' and os.environ['GITHUB_REF'] == 'refs/heads/main':
            reuse = resolve(repository, commit, args.directory)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
                stream.write('reuse=' + str(reuse).lower() + '\n')
        print('Riutilizzo runtime PR verificati' if reuse else 'Nuova verifica richiesta')
    elif args.action == 'record':
        if not args.component or not args.image:
            parser.error('record richiede --component e --image')
        digests = json.loads(run('docker', 'inspect', '--format', '{{json .RepoDigests}}', args.image))
        prefix = f'ghcr.io/{repository.lower()}-{args.component}@sha256:'
        matches = [s for s in digests if s.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError('Digest pubblicato ambiguo o assente')
        save(args.directory / (args.component + '.json'), {'metadata': metadata(), 'component': args.component, 'image': matches[0]})
    elif args.action == 'assemble':
        value = assemble(Path('reports/runtime'), metadata())
        save(args.directory / 'runtime-manifest.json', value)
    elif args.action == 'pull':
        value = validate_manifest(json.loads((args.directory / 'runtime-manifest.json').read_text()), repository,
                                  run('git', 'rev-parse', 'HEAD^{tree}'))
        for component, image in value['images'].items():
            subprocess.run(['docker', 'pull', image], check=True)
            run('docker', 'tag', image, f'righaven-{component}:0.1.0')
    elif args.action == 'seal':
        value = validate_manifest(json.loads((args.directory / 'runtime-manifest.json').read_text()), repository,
                                  run('git', 'rev-parse', 'HEAD^{tree}'))
        value.update(verified=True, compose_sha256=hashlib.sha256((args.directory / 'compose.hostinger.yaml').read_bytes()).hexdigest())
        save(args.directory / 'runtime-manifest.json', value)
        validate_bundle(args.directory, repository, value['tree'])
    else:
        publish(args.directory, repository, commit, os.environ['GITHUB_REF'] == 'refs/heads/main')


if __name__ == '__main__':
    main()
