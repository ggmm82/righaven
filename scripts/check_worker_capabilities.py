"""Real Docker proof that a workspace role cannot run disabled native CLIs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def inside():
    import os
    installed = {a['id']: a for a in json.loads(Path('/opt/righaven/installed.json').read_text())}
    policy=json.loads(Path('/job.json').read_text())['capability_policy']
    disabled=set(policy['blocked']) & set(installed)
    allowed=set(policy['allowed']) & set(installed)
    for identifier in disabled:
        command = installed[identifier]['binary']
        # All disabled pinned executables now live inside their application bundle.
        # Test the actual installed paths, including FreeCAD's bundled Python.
        assert Path(command).is_relative_to('/opt/righaven/apps/' + identifier)
        assert not Path(command).exists(), identifier + ' bundle remains exposed'
        try:
            result = subprocess.run([command, '-version' if identifier == 'ffmpeg' else '--version'], capture_output=True, timeout=15)
        except (FileNotFoundError, PermissionError):
            continue
        assert result.returncode == 126 and b'Disabled native capability' in result.stderr, identifier + ' was not blocked by the policy'
    for command in ('ffmpeg', 'ffprobe'):
        try:probe = subprocess.run(['/usr/bin/' + command, '-version'], capture_output=True)
        except (FileNotFoundError,PermissionError):continue
        assert probe.returncode == 126 and b'Disabled native capability' in probe.stderr
    for command in (['craft', 'list'], ['craft', 'capabilities']):
        records = json.loads(subprocess.check_output(command, text=True))
        assert not disabled & {r['id'] for r in records}
        assert {r['id'] for r in records}==allowed
    for identifier in disabled:
        result = subprocess.run(['craft', 'commands', identifier], capture_output=True, timeout=15)
        assert result.returncode != 0, identifier + ' bypassed craft policy'
    # FreeCAD is also callable as a Python module, not only as an executable.
    code = "import sys,importlib.util;sys.path[:0]=['/opt/righaven/apps/freecad/squashfs-root/usr/lib'];assert importlib.util.find_spec('FreeCAD') is None"
    assert subprocess.run(['/usr/bin/python3', '-c', code], capture_output=True).returncode == 0
    # The new Python tools must not leak into a shared interpreter.
    code = "import sys,importlib.util;apps=('ifcopenshell','manim','opentimelineio','pymeshlab');sys.path[:0]=['/opt/righaven/apps/'+a+'/venv/lib/python3.11/site-packages' for a in apps];assert all(importlib.util.find_spec(a) is None for a in apps)"
    assert subprocess.run(['/usr/bin/python3','-c',code],capture_output=True).returncode == 0
    for identifier in disabled:
        assert not Path('/mnt/skills/custom/skill-'+identifier+'/SKILL.md').exists(), identifier+' skill was not masked'
    assert allowed, 'The check needs an enabled native tool too'
    active=sorted(allowed)[0]
    assert subprocess.run([installed[active]['binary'], '-version' if active=='ffmpeg' else '--version'],capture_output=True).returncode==0
    print('Worker policy OK: empty-tools workspace, absolute binaries, FreeCAD Python API, CLI catalogs and active tool isolation')


def shared_browser_inside():
    assert not Path('/opt/righaven/toolkit/node_modules/playwright').exists()
    assert Path('/opt/righaven/playwright-browsers').is_dir()
    root=Path('/mnt/user-data/design-browser-proof');root.mkdir(parents=True)
    source=root/'model.mmd';source.write_text('flowchart LR\n a[Idea] --> b[Result]')
    subprocess.run(['mermaid-cli','call','render',json.dumps({'input':str(source),'output':str(root/'rendered')})],check=True,timeout=180)
    assert (root/'rendered/diagram.svg').is_file()
    print('Shared browser OK: Mermaid renders with Playwright automation disabled; no duplicate Chromium')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--inside', action='store_true'); parser.add_argument('--shared-browser', action='store_true')
    parser.add_argument('--no-shared-browser',action='store_true')
    parser.add_argument('--disabled',nargs='+')
    parser.add_argument('--image', default='righaven-sandbox:0.1.0'); args = parser.parse_args()
    if args.shared_browser:
        shared_browser_inside(); return
    if args.inside:
        inside(); return
    root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
    from righaven.capability_policy import policy_from_names, worker_arguments
    from righaven.state import applications
    disabled = {'blender', 'cadcraft', 'ffmpeg', 'freecad', 'musescore', 'ifcopenshell', 'manim', 'opentimelineio', 'pymeshlab', 'd2', 'plantuml', 'mermaid', 'excalidraw', 'bpmn', 'structurizr'}
    if args.disabled is not None:disabled=set(args.disabled)
    policy = policy_from_names({'skill-' + a['id'] for a in applications() if a['id'] not in disabled})
    with tempfile.TemporaryDirectory(prefix='worker-policy-') as folder:
        path = Path(folder); blocker = path / 'disabled'
        blocker.write_text('#!/bin/sh\necho "Disabled native capability" >&2\nexit 126\n'); blocker.chmod(0o755)
        job = path / 'job.json'
        job.write_text(json.dumps({'agent': 'workspace', 'role': {'tools': []}, 'capability_policy': policy}));job.chmod(0o644)
        subprocess.run(['docker', 'run', '--rm', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            *worker_arguments(policy, blocker), '--mount', f'type=bind,src={root},dst=/review,readonly',
            '--mount', f'type=bind,src={job},dst=/job.json,readonly', '--entrypoint', 'python3', args.image,
            '/review/scripts/check_worker_capabilities.py', '--inside'], check=True)
        if args.no_shared_browser:return
        shared=policy_from_names({'skill-mermaid','skill-typst'})
        job.write_text(json.dumps({'agent':'workspace','role':{'tools':['mermaid']},'capability_policy':shared}))
        subprocess.run(['docker','run','--rm','--init','--network=none','--memory=1536m','--cpus=1.5','--pids-limit=256','--cap-drop=ALL','--security-opt=no-new-privileges',
            *worker_arguments(shared,blocker),'--mount',f'type=bind,src={root},dst=/review,readonly',
            '--mount',f'type=bind,src={job},dst=/job.json,readonly','--entrypoint','python3',args.image,
            '/review/scripts/check_worker_capabilities.py','--shared-browser'],check=True)



if __name__ == '__main__': main()
