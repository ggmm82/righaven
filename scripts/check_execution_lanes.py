#!/usr/bin/env python3
"""Actual parallel Docker workers + preparation + interactive PTY under one resource budget."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import docker_runtime as runtime, state, environment_runtime as factory
from righaven.resource_budget import ResourceBudget
from righaven.resource_slot import ResourceSlot
from righaven.preparation_slots import PreparationSlots,TerminalSlots
from righaven.environment_terminal import Session,SESSIONS,close_client


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',default=runtime.IMAGE);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='execution-lanes-') as temporary:
        root=Path(temporary);(root/'installation-id').write_text(uuid.uuid4().hex)
        budget=ResourceBudget(elastic=True);worker=ResourceSlot();builder=PreparationSlots();terminal=TerminalSlots()
        limits={'cpus':max(.5,min(4,int(runtime.docker('info','--format','{{.NCPU}}'))-.5)),'memory_mib':4096,'tmp_mib':512,'threads':4,'max_workers':2}
        with patch.object(state,'STATE',root),patch.object(runtime,'host_path',side_effect=str),patch.object(runtime,'IMAGE',args.image),patch.object(runtime,'EXECUTION_LOCK',worker),patch.object(runtime,'BUILD_LOCK',builder),patch.object(runtime,'TERMINAL_LOCK',terminal),patch('righaven.runtime_settings.effective',return_value=limits),patch('righaven.resource_budget.BUDGET',budget):
            containers=[];console=None;second_console=None
            try:
                for i in range(2):
                    name='skill-lane-worker-'+uuid.uuid4().hex[:8];containers.append(name)
                    job_limits=budget.acquire(name,'worker',timeout=5)
                    subprocess.run(['docker',*runtime.base_arguments(name,job_limits),'-d',args.image,'sleep','60'],check=True,stdout=subprocess.DEVNULL)
                from righaven.resource_budget import BudgetBusy
                try:budget.acquire('third','worker',timeout=0)
                except BudgetBusy:pass
                else:raise AssertionError('Third worker exceeds configured resource budget')
                key,_=factory.recipe([])
                console=Session('test-owner','inspection',{'runtime':{'id':key},'skills':[]},{'allowed':[],'blocked':[],'skill_sources':{}},client_id='a'*32)
                console.write("printf 'console-%s\\n' independent\n")
                until=time.monotonic()+10
                while time.monotonic()<until and 'console-independent' not in console.public()['text']:time.sleep(.1)
                assert 'console-independent' in console.public()['text'],console.public()
                second_console=Session('test-owner','other-inspection',{'runtime':{'id':key},'skills':[]},{'allowed':[],'blocked':[],'skill_sources':{}},client_id='b'*32)
                second_console.write("printf 'second-%s\\n' console\n")
                until=time.monotonic()+10
                while time.monotonic()<until and 'second-console' not in second_console.public()['text']:time.sleep(.1)
                assert 'second-console' in second_console.public()['text'],second_console.public()
                assert all(n in budget.leases for n in containers)
                config=json.loads(subprocess.check_output(['docker','inspect',*containers,console.container,second_console.container],text=True))
                assert all(c['State']['Running'] for c in config)
                assert sum(c['HostConfig']['Memory'] for c in config)<=limits['memory_mib']*1048576
                assert sum(c['HostConfig']['NanoCpus'] for c in config)<=limits['cpus']*1e9
                SESSIONS[console.id]=console;SESSIONS[second_console.id]=second_console
                close_client('test-owner','a'*32)
                until=time.monotonic()+15
                while not console.closed and time.monotonic()<until:time.sleep(.1)
                assert console.closed and terminal.locked() and not second_console.closed
                second_console.write("printf 'still-%s\\n' usable\n")
                until=time.monotonic()+10
                while time.monotonic()<until and 'still-usable' not in second_console.public()['text']:time.sleep(.1)
                assert 'still-usable' in second_console.public()['text']
                assert all(n in budget.leases for n in containers),'Closing terminal released a worker'
                runtime.remove(containers.pop())
                assert builder.acquire()
                name='skill-lane-build-'+uuid.uuid4().hex[:8];containers.append(name)
                build_limits=budget.acquire(name,'build',timeout=5)
                subprocess.run(['docker',*runtime.base_arguments(name,build_limits),'-d',args.image,'sleep','60'],check=True,stdout=subprocess.DEVNULL)
                # Keep one real worker alive, switch to serial and apply live
                # quotas. No container restart or memory reduction is allowed.
                runtime.remove(containers.pop())
                limits['max_workers']=1
                before=json.loads(runtime.docker('inspect',containers[0]))[0]
                result=budget.rebalance()
                after=json.loads(runtime.docker('inspect',containers[0]))[0]
                expected=limits['cpus']-sum(v['cpus'] for v in budget.leases.values() if v['kind'] in ('terminal','control'))
                assert after['Id']==before['Id'] and after['State']['Running']
                assert abs(after['HostConfig']['NanoCpus']/1e9-expected)<.002,(result,after['HostConfig'])
                assert after['HostConfig']['Memory']>=before['HostConfig']['Memory']
                assert budget.snapshot()['allocated_cpus']<=limits['cpus']
                second_console.cancelled.set()
                until=time.monotonic()+15
                while not second_console.closed and time.monotonic()<until:time.sleep(.1)
                assert second_console.closed
                final=json.loads(runtime.docker('inspect',containers[0]))[0]
                assert abs(final['HostConfig']['NanoCpus']/1e9-limits['cpus'])<.002
                print('Elastic live budget OK: serial worker receives idle CPU, Docker container ID unchanged, RAM never reduced, active console remains reserved.')
                print('Parallel Docker OK: two workers and two real PTYs within aggregate limits; third waits; closing one terminal preserves the other console and workers; preparation uses freed resources.')
            finally:
                if second_console and not second_console.closed:
                    second_console.cancelled.set()
                    until=time.monotonic()+15
                    while not second_console.closed and time.monotonic()<until:time.sleep(.1)
                if console and not console.closed:
                    console.cancelled.set()
                    until=time.monotonic()+15
                    while not console.closed and time.monotonic()<until:time.sleep(.1)
                for name in containers:runtime.remove(name)
                if worker.locked():worker.release()
                if builder.locked():builder.release()


if __name__=='__main__':main()
