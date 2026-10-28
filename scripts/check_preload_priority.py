#!/usr/bin/env python3
"""Real Docker regression: a cold preload must yield to an already usable tool.

A controlled sleeping preparation stands in for a long compiler, only in this
test. Cleanup, cache preparation/reuse, foreground execution and retry are real.
"""
import argparse,json,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import state,environment_runtime as factory,docker_runtime as runtime
from righaven.execution_queue import ExecutionQueue
from righaven.resource_slot import ResourceSlot,PreparationCancel
from righaven.progress import create_job


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--terminal',action='store_true');args=parser.parse_args()
    slot=ResourceSlot(idle_seconds=.05);cancel=threading.Event();started=threading.Event()
    errors=[];deferred=[];delayed=[];completed=[]
    popen=subprocess.Popen
    def controlled(argv,*args,**kwargs):
        if isinstance(argv,list) and '/opt/righaven/prepare_environment.py' in argv and not delayed:
            delayed.append(True)
            index=argv.index('/opt/righaven/prepare_environment.py')
            argv=argv[:index-1]+['python3','-c',"import time;print('CI: controlled long preparation',flush=True);time.sleep(60)"]
        return popen(argv,*args,**kwargs)
    with tempfile.TemporaryDirectory(prefix='preload-priority-') as directory:
        root=Path(directory);(root/'installation-id').write_text(uuid.uuid4().hex)
        with patch.object(state,'STATE',root),patch.object(runtime,'BUILD_LOCK',slot),patch.object(runtime,'host_path',lambda p:str(p)),patch.object(factory,'pinned',return_value=set()):
            ready=factory.ensure(['d2']);key,_=factory.recipe(['pandoc'])
            def background():
                try:
                    while not cancel.is_set():
                        yielded=threading.Event()
                        if not slot.acquire_background(cancel,yielded):return
                        started.set()
                        try:
                            result=factory.ensure(['pandoc'],acquire=False,cancel=PreparationCancel(cancel,yielded))
                            completed.append(result);return
                        except factory.PreparationDeferred:
                            deferred.append(factory.read(key)['status'])
                        finally:slot.release()
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=background,daemon=True)
            try:
                with patch('righaven.environment_runtime.subprocess.Popen',side_effect=controlled):
                    thread.start();assert started.wait(5)
                    until=time.monotonic()+15
                    while time.monotonic()<until:
                        if factory.docker('ps','-q','--filter','label=org.righaven.environment='+key):break
                        time.sleep(.1)
                    else:raise AssertionError('Controlled preparation container did not start')
                    progress=create_job(root/'chat','rh-job-123456abcdef','workspace','codex','test')
                    start=time.monotonic()
                    assert slot.acquire_terminal(timeout=15) if args.terminal else ExecutionQueue().acquire(slot,progress,root,lambda:False)
                    try:
                        assert time.monotonic()-start<15,'Foreground waited for the entire long preparation'
                        assert deferred==['waiting_chat'],deferred
                        assert not factory.docker('ps','-aq','--filter','label=org.righaven.environment='+key)
                        assert not list(factory.folder().glob('*.request.json'))
                        assert factory.ensure(['d2'],acquire=False)['image_id']==ready['image_id']
                        # Execute the genuine native binary from the already-ready image.
                        code="import json,subprocess;v=json.load(open('/opt/righaven/installed.json'));subprocess.run([v[0]['binary'],'--version'],check=True)"
                        print(factory.docker('run','--rm','--network=none',ready['image_id'],'python3','-c',code))
                        assert not completed,'Optional preparation overlapped the foreground command'
                    finally:slot.release()
                    thread.join(60);assert not thread.is_alive(),'Preparation did not resume'
                    assert not errors,errors
                    assert completed and factory.image_exists(completed[0])
                    assert not factory.docker('ps','-aq','--filter','label=org.righaven.environment='+key)
                    print(('Terminal' if args.terminal else 'Chat')+' priority Docker OK: cold preload interrupted and removed; ready tool ran first; verified cache preserved; preload resumed and verified.')
            finally:
                cancel.set();thread.join(10)
                for path in factory.folder().glob('*.json'):
                    if len(path.stem)==64:
                        value=factory.read(path.stem)
                        if value and value.get('container'):
                            runtime.remove(value['container'])
                        if value and value.get('status')=='ready':factory.evict(path.stem)


if __name__=='__main__':main()
