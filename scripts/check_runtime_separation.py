#!/usr/bin/env python3
"""Real software-only candidate: update worker code without reinstalling D2."""
import json, os, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from righaven import state, runtime_bundle as bundle, docker_runtime as runtime, environment_runtime as factory


def main():
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='runtime-separation-') as directory:
        root = Path(directory); persistent = root / 'state'; persistent.mkdir()
        (persistent / 'installation-id').write_text(uuid.uuid4().hex)
        source = root / 'release'; (source / 'config').mkdir(parents=True)
        manifest = repo / 'config/worker-bundle.json'
        shutil.copy2(manifest, source / 'config/worker-bundle.json')
        for section in json.loads(manifest.read_text()).values():
            for relative in section.values():
                target = source / relative; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(repo / relative, target)
        shutil.copytree(repo/'config',source/'config',dirs_exist_ok=True)
        shutil.copytree(repo/'docker',source/'docker')
        shutil.copy2(repo/'versions.lock.json',source/'versions.lock.json')
        shutil.copy2(repo/'righaven/docker_archives.py',source/'righaven/docker_archives.py')
        for name in ('install_antigravity.py','antigravity.lock.json','claude.lock.json','install_righaven.py','install_system_packages.py','check_provider_clis.py','build_design_web.cjs','StructurizrJob.java','package_environment_image.py'):
            shutil.copy2(repo/'scripts'/name,source/'scripts'/name)
        env = {'RIGHAVEN_WORKER_SOURCE': str(source), 'RIGHAVEN_BUNDLED_SKILLS': str(repo / 'skills')}
        with patch.dict(os.environ, env), patch.object(state, 'STATE', persistent), patch.object(runtime, 'host_path', side_effect=str), patch.object(factory, 'pinned', return_value=set()):
            ready = None
            try:
                ready = factory.ensure(['d2'], exact=True)
                first = bundle.stage()
                # A committed software environment must not contain mounted release code or skills.
                script = 'from pathlib import Path; assert not Path("/opt/righaven-worker/run_agent.py").exists(); assert not Path("/opt/righaven/craft.py").read_bytes(); assert not Path("/mnt/skills/custom").exists()'
                subprocess.run(['docker','run','--rm','--network=none',ready['image_id'],'python3','-c',script],check=True)
                # Both the actual worker verifier and app adapters run with code mounted read-only.
                for command in (['python3','/opt/righaven-worker/handoff.py','schema'], ['craft','tools','d2']):
                    subprocess.run(['docker','run','--rm','--network=none',*bundle.arguments(),ready['image_id'],*command],check=True,stdout=subprocess.DEVNULL)
                path = source / 'righaven/run_agent.py'; path.write_text(path.read_text()+'\n# Simulated next worker release\n')
                second = bundle.stage(); assert first != second
                popen=subprocess.Popen
                def no_install(argv,*args,**kwargs):
                    if '/opt/righaven/prepare_environment.py' in argv:raise AssertionError('Cache reuse must not reinstall tools')
                    return popen(argv,*args,**kwargs)
                with patch.object(factory.subprocess,'Popen',side_effect=no_install):
                    again = factory.ensure(['d2'], exact=True)
                assert again['id']==ready['id'] and again['image_id']==ready['image_id']
                # The old active bundle is retained, while the next job mounts the updated worker.
                assert not (first/'righaven-worker/run_agent.py').read_text().endswith('# Simulated next worker release\n')
                assert (second/'righaven-worker/run_agent.py').read_text().endswith('# Simulated next worker release\n')
                # Exercise the same administrator verification queue used by the UI.
                # A second D2 release must coexist with the original cached recipe.
                from righaven import tool_versions
                import time
                original=ready
                def verify_release(tool,version):
                    job=tool_versions.start(tool,version)
                    status_path=tool_versions.directory()/'jobs'/job['id']/'status.json'
                    deadline=time.monotonic()+1200
                    while time.monotonic()<deadline:
                        status=json.loads(status_path.read_text())
                        if status['state']=='failed':
                            for failed in factory.folder().glob('*.json'):
                                if json.loads(failed.read_text()).get('status')=='failed':print(factory.preparation_text(failed.stem),flush=True)
                            raise AssertionError(status)
                        if status['state']=='ready':return status['revision']
                        time.sleep(.25)
                    raise AssertionError('Release verification did not finish: '+tool)
                version=verify_release('d2','v0.7.0')
                ready=factory.ensure(['d2'],exact=True,versions={'d2':version})
                assert ready['id']!=original['id']
                with patch.object(factory.subprocess,'Popen',side_effect=no_install):
                    rollback=factory.ensure(['d2'],exact=True)
                assert rollback['image_id']==original['image_id']
                command=['docker','run','--rm','--network=none',ready['image_id'],'/opt/righaven/apps/d2/bin/d2','--version']
                assert '0.7.0' in subprocess.check_output(command,text=True)
                factory.evict(original['id'])
                from righaven import provider_bundle
                defaults=tool_versions.directory()/'defaults.json'
                for provider in ('provider-agy','provider-codex'):
                    pin=verify_release(provider,'1.4.8' if provider=='provider-agy' else tool_versions.builtins()[provider]['version'])
                    cli=factory.ensure([],versions={provider:pin})
                    assert cli['versions'][provider]==pin
                    # Model CLI pins are not part of program environments: D2 is reused untouched.
                    with patch.object(factory.subprocess,'Popen',side_effect=no_install):
                        same=factory.ensure(['d2'],exact=True,versions={'d2':version})
                    assert same['image_id']==ready['image_id'],same
                    engine='gemini' if provider=='provider-agy' else 'codex'
                    command='agy' if provider=='provider-agy' else 'codex'
                    # Workers run the CLI from a read-only bundle mounted over the program image.
                    for selected in (pin,None):
                        if selected:state.atomic_json(defaults,{provider:selected})
                        else:defaults.unlink()
                        mounted=provider_bundle.prepare(engine)
                        expected=(tool_versions.packages({provider:selected})[provider]['app'] if selected else tool_versions.builtins()[provider])['version']
                        assert mounted[1]['version']==expected,mounted
                        arguments=provider_bundle.arguments(mounted)
                        actual=runtime.docker('run','--rm','--network=none',*arguments,ready['image_id'],command,'--version')
                        assert expected.lstrip('v') in actual,actual
                        target=runtime.docker('run','--rm','--network=none',*arguments,ready['image_id'],'sh','-c','command -v '+command)
                        assert target==provider_bundle.TARGET+'/bin/'+command,target
                    factory.evict(cli['id'])
                print('Tool versions Docker OK: official release resolver, two D2 versions, rollback without reinstall, native Codex and Antigravity CLI verification.')
                from righaven.environment_portability import export_image,import_image
                exporting=root/'export';exporting.mkdir()
                # Force the exact class of platform-selection failures observed
                # on production. The fallback must still export a real complete
                # image that subsequently rebuilds and imports natively.
                from righaven import docker_archives
                original_run=subprocess.run;fallback=[]
                def incompatible_platform(argv,*args,**kwargs):
                    if argv[:3]==['docker','image','save'] and '--platform' in argv:
                        argv=list(argv);argv[argv.index('--platform')+1]='linux/arm64';fallback.append(True)
                    return original_run(argv,*args,**kwargs)
                with patch.object(docker_archives.subprocess,'run',side_effect=incompatible_platform):
                    archive=export_image(ready,exporting)
                assert fallback,'Platform compatibility fallback was not exercised'
                print('Provider cache reuse OK: custom CLI pins retain D2 without reinstalling it; mounted CLI bundles report native versions. Complete export fallback exercised against the real Docker engine.')
                # Rebuild the exported Dockerfile against the exact installed software base.
                import tarfile
                with tarfile.open(archive,'r:') as package:
                    package.extractall(root/'recipe',members=[member for member in package if member.name.startswith('rebuild')],filter='data')
                context=root/'recipe/rebuild';rebuilt='skill-rebuilt-check:'+uuid.uuid4().hex[:12]
                try:
                    context_name=factory.docker('context','show')
                    subprocess.run(['docker','buildx','build','--builder',context_name,'--load','--progress=plain',
                        '--build-arg','SOFTWARE_IMAGE='+runtime.IMAGE,'--tag',rebuilt,str(context)],check=True,timeout=600)
                    subprocess.run(['docker','run','--rm','--network=none',*bundle.arguments(),rebuilt,'craft','tools','d2'],check=True,stdout=subprocess.DEVNULL)
                    rebuilt_package=root/'rebuilt.righaven-env.tar'
                    subprocess.run([sys.executable,str(context/'package.py'),rebuilt,'--base',runtime.IMAGE,'--output',str(rebuilt_package)],check=True,timeout=300)
                    from righaven.environment_portability import unpack
                    verification=root/'rebuilt-verify';verification.mkdir()
                    metadata,_=unpack(rebuilt_package,verification)
                    assert metadata['source_image_id']==factory.docker('image','inspect',rebuilt,'--format','{{.Id}}')
                    print('Rebuild Docker OK: exported Dockerfile built actual locked D2; native workflow passed; bundled packager produced a valid import archive.')
                finally:
                    subprocess.run(['docker','image','rm','--no-prune',rebuilt],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                other=root/'other-installation';other.mkdir();(other/'installation-id').write_text(uuid.uuid4().hex)
                importing=root/'import';importing.mkdir()
                with patch.object(state,'STATE',other):
                    imported=import_image(archive,importing,['d2'])
                    try:
                        assert imported['imported'] and factory.image_exists(imported)
                        assert imported['versions']=={'d2':version}
                        assert tool_versions.read(version)['state']=='ready'
                        assert imported['id']==ready['id']
                        assert imported['image_id']!=ready['image_id'],'Ownership must be rebound to the destination installation'
                        print('Portability Docker OK: real image exported with Dockerfiles; imported under a different installation ID; current native checks passed; target cache registered.')
                    finally:factory.evict(imported['id'])
                from righaven.environment_terminal import Session,get,SESSIONS
                import time
                policy={'allowed':['d2'],'blocked':[a['id'] for a in state.applications() if a['id']!='d2'],
                    'skill_sources':{name:repo/'skills/custom'/name for name in ('skill-d2','skill-workspace')}}
                profile={'runtime':{'id':ready['id']},'skills':['skill-d2','skill-workspace']}
                console=Session('owner','d2',profile,policy);SESSIONS[console.id]=console
                try:
                    try:get('another-owner',console.id)
                    except FileNotFoundError:pass
                    else:raise AssertionError('Terminal session leaked to another account')
                    # Split marker avoids mistaking echoed input for executed output.
                    console.write("test ! -e /credentials && test ! -e /var/run/docker.sock && printf 'terminal-%s\\n' isolated\n")
                    until=time.monotonic()+30
                    while time.monotonic()<until and 'terminal-isolated' not in console.public()['text']:time.sleep(.2)
                    assert 'terminal-isolated' in console.public()['text'],console.public()
                    console.resize(100,40)
                    until=time.monotonic()+10
                    while time.monotonic()<until:
                        dimensions=factory.docker('exec',console.container,'stty','-F','/dev/pts/0','size')
                        if dimensions=='40 100':break
                        time.sleep(.1)
                    else:raise AssertionError('Docker PTY dimensions did not follow SIGWINCH: '+dimensions)
                    console.write("printf '\\033[31mansi-red\\033[0m\\n'\n")
                    until=time.monotonic()+10
                    import base64
                    while time.monotonic()<until:
                        if b'\x1b[31mansi-red\x1b[0m' in base64.b64decode(console.public(0)['output_base64']):break
                        time.sleep(.1)
                    else:raise AssertionError('PTY output lost ANSI sequences')
                    print('Interactive PTY OK: Docker terminal resized to 100x40 and raw ANSI bytes preserved.')
                    print('Terminal Docker OK: actual PTY command executed; no credential or socket mounts; cross-account access rejected.')
                finally:
                    console.cancelled.set()
                    until=time.monotonic()+15
                    while not console.closed and time.monotonic()<until:time.sleep(.1)
                    assert console.closed and not runtime.TERMINAL_LOCK.locked(),'Terminal did not release its independent console slot'
                    assert not factory.docker('ps','-aq','--filter','name='+console.container)
                    SESSIONS.pop(console.id,None)
                saved=root/'saved-source.txt';saved.write_text('Keep source and lesson data')
                runtime.release_prepared_environment(ready,True)
                assert factory.read(ready['id'])['status']=='on_demand'
                assert not factory.image_exists(factory.read(ready['id']))
                assert saved.read_text()=='Keep source and lesson data'
                assert factory.docker('image','inspect',runtime.IMAGE,'--format','{{.Id}}')
                ready=None
                print('Ephemeral cache Docker OK: prepared app image removed, stable software base and saved data preserved.')
                print('Software separation OK: native D2 verified, committed image contains no worker/skills; adapters execute through read-only mounts; changed worker reuses identical environment without installation; old bundle preserved.')
            finally:
                if ready:factory.evict(ready['id'])


if __name__=='__main__':main()
