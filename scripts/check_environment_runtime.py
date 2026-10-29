#!/usr/bin/env python3
"""Real Docker factory check on the exact core candidate; no AI credentials."""
import argparse,json,os,sys,tempfile,uuid,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import state, environment_runtime as factory, docker_runtime as runtime


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tools',nargs='+',default=['d2'])
    parser.add_argument('--team-check',action='store_true')
    parser.add_argument('--calibre-stress',action='store_true')
    parser.add_argument('--incremental-check',action='store_true')
    parser.add_argument('--policy-check',action='store_true')
    parser.add_argument('--recovery-check',action='store_true')
    parser.add_argument('--verification-dependencies',action='store_true')
    args=parser.parse_args()
    requested=sorted(set(args.tools))
    if args.verification_dependencies:
        from scripts.prepare_environment import VERIFICATION_DEPENDENCIES
        for tool in list(requested):requested.extend(VERIFICATION_DEPENDENCIES.get(tool,[]))
    selected=factory.closure(requested)
    label=runtime.IMAGE
    inspected=json.loads(factory.docker('image','inspect',label))[0]
    assert inspected['Config']['Labels']['org.righaven.runtime.kind']=='core'
    installed=factory.docker('run','--rm','--network=none',label,'cat','/opt/righaven/installed.json')
    assert json.loads(installed)==[], 'Core must not preload native apps'
    with tempfile.TemporaryDirectory(prefix='skill-environments-') as directory:
        root=Path(directory);(root/'installation-id').write_text(uuid.uuid4().hex)
        made=[]
        try:
            # Host check uses host paths; production Gateway uses its volume translation.
            with patch.object(state,'STATE',root),patch.object(runtime,'host_path',lambda p:str(p)),patch.object(factory,'pinned',return_value=set()):
                empty=factory.ensure([]);assert empty['core'] and empty['image']==label
                if args.incremental_check:
                    assert {'d2','pandoc'}.issubset(selected)
                    parent=factory.ensure(['d2']);made.append(parent)
                from righaven.progress import update
                progress=root/'foreground-progress.json';update(progress,'planning')
                try:ready=factory.ensure(selected,progress=progress)
                except Exception:
                    for log in (root/'environments').glob('*.log'):
                        print(log.read_text()[-12000:],file=sys.stderr)
                    raise
                made.append(ready)
                assert ready['tools']==selected and ready['status']=='ready'
                proof=json.loads(factory.docker('run','--rm','--network=none',ready['image_id'],'cat','/opt/righaven/environment.json'))
                if args.incremental_check:
                    assert proof['reused_tools']==['d2'],proof
                    assert proof['installed_tools']==['pandoc'],proof
                    assert ready['base_image_id']==parent['image_id'],ready
                assert proof['verified'] and set(args.tools).issubset(proof['checks']['native_workflows']),proof
                records=json.loads(factory.docker('run','--rm','--network=none',ready['image_id'],'cat','/opt/righaven/installed.json'))
                assert {a['id'] for a in records}==set(selected),records
                again=factory.ensure(selected);assert ready['image_id']==again['image_id']
                assert not factory.docker('ps','-aq','--filter','label=org.righaven.environment='+ready['id'])
                assert not list(root.rglob('*.request.json'))
                if args.policy_check:
                    assert {'d2','pandoc'}.issubset(selected)
                    subprocess.run([sys.executable,str(Path(__file__).with_name('check_worker_capabilities.py')),'--image',ready['image_id'],'--disabled','d2','--no-shared-browser'],check=True)
                if args.team_check:
                    assert {'photocraft','effectcraft','soundcraft','filmcraft','ffmpeg'}.issubset(selected)
                    repo=Path(__file__).resolve().parents[1]
                    subprocess.run(['docker','run','--rm','--init','--network=none','--memory=1536m','--cpus=1.5','--pids-limit=256','--cap-drop=ALL','--security-opt=no-new-privileges','--mount','type=bind,src='+str(repo)+',dst=/review,readonly',ready['image_id'],'python3','/review/scripts/check_team_pipeline.py','--output','/mnt/user-data/outputs/team-acceptance','--simulate-audio-interruption'],check=True)
                if args.calibre_stress:
                    assert {'calibre','pdfcraft'}.issubset(selected)
                    repo=Path(__file__).resolve().parents[1]
                    subprocess.run(['docker','run','--rm','--init','--network=none','--memory=1536m','--cpus=1.5','--pids-limit=256','--cap-drop=ALL','--security-opt=no-new-privileges','--mount','type=bind,src='+str(repo/'scripts')+',dst=/review,readonly',ready['image_id'],'python3','/review/check_calibre_headless.py'],check=True)
                    subprocess.run(['docker','run','--rm','--init','--network=none','--memory=2048m','--memory-swap=2048m','--cpus=0.875','--pids-limit=256','--ulimit','core=0:0','--cap-drop=ALL','--security-opt=no-new-privileges','--env','RIGHAVEN_CPU_THREADS=1','--mount','type=bind,src='+str(repo/'scripts')+',dst=/review,readonly',ready['image_id'],'python3','/review/check_calibre_render_recovery.py'],check=True)
                if args.recovery_check:
                    repo=Path(__file__).resolve().parents[1]
                    subprocess.run(['docker','run','--rm','--init','--network=none','--memory=1536m','--cpus=1.5','--pids-limit=256','--cap-drop=ALL','--security-opt=no-new-privileges','--entrypoint','python3','--mount','type=bind,src='+str(repo/'scripts')+',dst=/review,readonly',ready['image_id'],'/review/check_artifact_recovery.py'],check=True)

                if 'axe-core' in requested:
                    subprocess.run([sys.executable,str(Path(__file__).with_name('check_extended_worker_scope.py')),ready['image_id']],check=True)

                assert factory.evict(ready['id'])['removed']
                if args.incremental_check:assert factory.evict(parent['id'])['removed']
                made.clear()
                assert factory.read(ready['id'])['status']=='on_demand'
            print('Core factory OK: selected native workflows',selected,'; reuse, source verification, isolation and cleanup passed.')
        finally:
            for item in reversed(made):
                try:factory.docker('image','rm','--no-prune',item['image'])
                except Exception:pass


if __name__=='__main__':main()
