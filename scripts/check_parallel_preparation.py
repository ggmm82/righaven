#!/usr/bin/env python3
"""Two real independent native builds; shared dependency cold start without deadlock."""
import argparse,json,subprocess,sys,tempfile,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import state,environment_runtime as factory,docker_runtime as runtime
from righaven.preparation_slots import PreparationSlots
from righaven.resource_budget import ResourceBudget


def phase(image,shared=False):
    with tempfile.TemporaryDirectory(prefix='parallel-native-preparation-') as temporary:
        root=Path(temporary);(root/'installation-id').write_text(uuid.uuid4().hex)
        limits={'cpus':4,'memory_mib':4096,'threads':4,'tmp_mib':512,'max_workers':1 if shared else 2}
        slots=PreparationSlots();budget=ResourceBudget();cancel=threading.Event();launches=[];guard=threading.Lock();observed=False
        original=subprocess.Popen
        def launch(argv,*args,**kwargs):
            if isinstance(argv,list) and '/opt/righaven/prepare_environment.py' in argv:
                name=argv[argv.index('--name')+1]
                with guard:launches.append(name)
                index=argv.index('/opt/righaven/prepare_environment.py')
                program,request=argv[index:index+2]
                code='import time,sys,runpy;sys.path.insert(0,"/opt/righaven");time.sleep(3);sys.argv='+repr([program,request])+';runpy.run_path('+repr(program)+',run_name="__main__")'
                argv=argv[:index-1]+['python3','-c',code]
            return original(argv,*args,**kwargs)
        dependencies={**factory.DEPS,**({'d2':['pandoc']} if shared else {})}
        with patch.object(state,'STATE',root),patch.object(runtime,'IMAGE',image),patch.object(runtime,'BUILD_LOCK',slots),patch.object(runtime,'host_path',side_effect=str),patch.object(factory,'pinned',return_value=set()),patch.object(factory,'DEPS',dependencies),patch('righaven.runtime_settings.effective',return_value=limits),patch('righaven.resource_budget.BUDGET',budget),patch.object(factory.subprocess,'Popen',side_effect=launch):
            try:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    futures=[pool.submit(factory.ensure,tools,exact=True,cancel=cancel) for tools in (['d2'],['pandoc'],['d2'])]
                    until=time.monotonic()+240
                    while not all(f.done() for f in futures):
                        if time.monotonic()>until:
                            cancel.set();raise TimeoutError('Parallel preparation did not finish')
                        with budget.condition:names=[k for k,v in budget.leases.items() if v['kind']=='build']
                        if len(names)==2:
                            inspection=subprocess.run(['docker','inspect',*names],capture_output=True,text=True)
                            states=json.loads(inspection.stdout) if not inspection.returncode else []
                            if len(states)==2 and all(v['State']['Running'] for v in states):
                                observed=True
                                assert sum(v['HostConfig']['Memory'] for v in states)<=4096*1048576
                                assert sum(v['HostConfig']['NanoCpus'] for v in states)<=4e9
                        time.sleep(.1)
                    try:results=[f.result() for f in futures]
                    except BaseException:
                        for file in factory.folder().glob('*.log'):print(file.name+'\n'+file.read_text()[-6000:],file=sys.stderr)
                        raise
                assert len(launches)==2,launches
                assert results[0]['image_id']==results[2]['image_id']
                if not shared:assert observed,'Two independent preparation containers never ran together'
                assert not slots.locked() and not budget.leases and not factory._RECIPE_LOCKS
                for result in results:
                    proof=json.loads(runtime.docker('run','--rm','--network=none',result['image_id'],'cat','/opt/righaven/environment.json'))
                    assert proof['verified'] and set(result['tools']).issubset(proof['checks']['native_workflows']),proof
                print('Shared dependency native OK: single-slot cold D2/Pandoc, no duplicate installation or admission deadlock.' if shared else 'Parallel native OK: two real D2/Pandoc preparations observed running together within total limits; repeated D2 request reuses one image.')
            finally:
                for name in launches:
                    try:runtime.remove(name)
                    except Exception:pass
                for file in factory.folder().glob('*.json'):
                    try:
                        record=factory.read(file.stem)
                        if record and record.get('status')=='ready':factory.evict(record['id'])
                    except (ValueError,subprocess.SubprocessError):pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',default=runtime.IMAGE);args=parser.parse_args()
    phase(args.image);phase(args.image,shared=True)


if __name__=='__main__':main()
