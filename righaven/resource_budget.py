"""Shared admission with elastic CPU and protected memory for control lanes."""
import json
import math
import subprocess
import threading
import time
from . import runtime_settings


class BudgetBusy(RuntimeError):
    pass


def update_container_limits(owner,cpus,memory_mib=None):
    args=['docker','update','--cpus='+str(cpus)]
    if memory_mib is not None:args+=['--memory='+str(memory_mib)+'m','--memory-swap='+str(memory_mib)+'m']
    try:result=subprocess.run([*args,owner],capture_output=True,text=True,timeout=8)
    except subprocess.TimeoutExpired:result=None
    inspected=subprocess.run(['docker','inspect','--format','{{json .HostConfig}}',owner],capture_output=True,text=True,timeout=5)
    if inspected.returncode:
        if 'No such' in inspected.stderr:return None
        raise RuntimeError('Quota Docker non verificabile')
    value=json.loads(inspected.stdout)
    actual=value.get('NanoCpus',0)/1e9
    if not actual and value.get('CpuPeriod',0)>0:actual=value.get('CpuQuota',0)/value['CpuPeriod']
    if actual<=0 or value.get('Memory',0)<=0:raise RuntimeError('Quota Docker non limitata')
    return {'cpus':actual,'memory_mib':value['Memory']//1048576,
            'confirmed':result is not None and result.returncode==0}


def console_capacity(value):
    memory=min(256,value['memory_mib']//4);cpu=min(.25,value['cpus']/4)
    return max(1,min(value.get('max_workers',2),memory//128,int(cpu/.125)))


class ResourceBudget:
    def __init__(self,*,elastic=False,updater=None):
        self.condition = threading.Condition()
        self.leases = {}
        self.waiters = {}
        self.blocked = ''
        self.elastic=elastic
        self.updater=updater or update_container_limits

    def observe_progress(self,owner,path):
        with self.condition:
            if owner in self.leases:self.leases[owner]['progress_path']=str(path)

    def _set_limits(self,owner,cpu,memory=None):
        value=self.leases[owner]
        try:
            actual=self.updater(owner,cpu,memory)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):
            # An update may have reached Docker despite a lost reply. Reserve
            # the upper bound until a later inspection confirms the allocation.
            value['cpus']=max(value['cpus'],cpu)
            if memory is not None:value['memory_mib']=max(value['memory_mib'],memory)
            value['quota_unconfirmed']=True
            return False
        if actual is None:return False  # Container not launched or already removed.
        value.update(cpus=actual['cpus'],memory_mib=actual['memory_mib'],quota_unconfirmed=not actual.get('confirmed',True))
        if value.get('progress_path'):
            try:
                from .progress import read_status,update
                path=value['progress_path'];limits=read_status(path).get('limits',{})
                update(path,limits={**limits,'cpus':value['cpus'],'memory_mib':value['memory_mib']})
            except (OSError,ValueError):pass
        return actual.get('confirmed',True)

    def _rebalance_locked(self,*,extra_cpu=0,pending_heavy=0,grow_memory=False):
        total=runtime_settings.effective()
        heavy=[(k,v) for k,v in self.leases.items() if v['kind'] not in ('terminal','control')]
        other=[v for v in self.leases.values() if v['kind'] in ('terminal','control')]
        pool=max(0,total['cpus']-sum(v['cpus'] for v in other)-extra_cpu)
        share=math.floor(pool/max(1,len(heavy)+pending_heavy)*1000)/1000
        memory_pool=total['memory_mib']-max(min(256,total['memory_mib']//4)+min(512,total['memory_mib']//4),sum(v['memory_mib'] for v in other))
        target_memory=memory_pool//max(1,len(heavy),total.get('max_workers',2))
        updated=failed=unchanged=0
        # Reduce quotas before increasing peers, keeping aggregate admission safe.
        for owner,value in sorted(heavy,key=lambda item:item[1]['cpus']-share,reverse=True):
            cpu=share
            if cpu>value['cpus']:
                free=pool-sum(v['cpus'] for key,v in heavy if key!=owner)
                cpu=min(cpu,max(value['cpus'],free))
            memory=None
            if grow_memory:
                desired=target_memory
                free=memory_pool-sum(v['memory_mib'] for key,v in heavy if key!=owner)
                desired=min(desired,free)
                if desired>value['memory_mib']:memory=desired
            if cpu<.001:failed+=1;continue
            if abs(cpu-value['cpus'])<.0009 and memory is None and not value.get('quota_unconfirmed'):
                unchanged+=1;continue
            if self._set_limits(owner,cpu,memory):updated+=1
            else:failed+=1
        return {'updated':updated,'unchanged':unchanged,'pending':failed,
                'memory_deferred':sum(v['memory_mib']>max(0,target_memory) for _,v in heavy)}

    def rebalance(self):
        with self.condition:
            result=self._rebalance_locked(grow_memory=True)
            self.condition.notify_all()
            return result

    def acquire(self, owner, kind, *, cancel=None, timeout=None, exact=None):
        token = object()
        with self.condition:
            self.waiters[token] = kind
        try:
            return self._acquire(owner, kind, cancel=cancel, timeout=timeout, exact=exact)
        finally:
            with self.condition:
                self.waiters.pop(token, None)

    def snapshot(self):
        """Installation totals only: never expose container/account identifiers."""
        with self.condition:
            total = runtime_settings.effective()
            used = list(self.leases.values())
            return {'observed_at': time.time(), 'configured_limit': total.get('max_workers', 2),
                'cpus': total['cpus'], 'memory_mib': total['memory_mib'],
                'allocated_cpus': round(sum(v['cpus'] for v in used), 3),
                'allocated_memory_mib': sum(v['memory_mib'] for v in used),
                'active': {kind: sum(v['kind'] == kind for v in used) for kind in ('worker','build','terminal','control')},
                'waiting': {kind: sum(v == kind for v in self.waiters.values()) for kind in ('worker','build','terminal','control')},
                'blocked': bool(self.blocked),'elastic_cpu':self.elastic,'quota_unconfirmed':sum(bool(v.get('quota_unconfirmed')) for v in used)}

    def _acquire(self, owner, kind, *, cancel=None, timeout=None, exact=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self.condition:
            while True:
                if owner in self.leases: raise ValueError('Risorse già riservate')
                if cancel and cancel.is_set(): raise RuntimeError('Attesa risorse annullata')
                if self.blocked: raise RuntimeError(self.blocked)
                total = runtime_settings.effective()
                console_memory = min(256, total['memory_mib'] // 4)
                console_cpu = min(.25, total['cpus'] / 4)
                control_memory=min(512,total['memory_mib']//4)
                control_cpu=min(.5,total['cpus']/4)
                used = list(self.leases.values())
                if kind in ('terminal','control'):
                    terminal_slots=console_capacity(total)
                    memory,cpu=(console_memory//terminal_slots,console_cpu/terminal_slots) if kind=='terminal' else (control_memory,control_cpu)
                    if self.elastic and sum(v['kind']==kind for v in used)<(terminal_slots if kind=='terminal' else 1) and sum(v['memory_mib'] for v in used)+memory<=total['memory_mib']:
                        self._rebalance_locked(extra_cpu=cpu)
                        used=list(self.leases.values())
                    available = (sum(v['kind']==kind for v in used)<(terminal_slots if kind=='terminal' else 1)
                        and sum(v['memory_mib'] for v in used) + memory <= total['memory_mib']
                        and sum(v['cpus'] for v in used) + cpu <= total['cpus'])
                else:
                    heavy = [v for v in used if v['kind'] not in ('terminal','control')]
                    free_memory = total['memory_mib'] - console_memory - control_memory - sum(v['memory_mib'] for v in heavy)
                    free_cpu = total['cpus'] - console_cpu - control_cpu - sum(v['cpus'] for v in heavy)
                    ceiling = total['memory_mib'] - console_memory - control_memory
                    slots=max(1,min(total.get('max_workers',2),max(1,ceiling//512),max(1,int((total['cpus']-console_cpu-control_cpu)/.25))))
                    share_memory=ceiling//slots
                    share_cpu=(total['cpus']-console_cpu-control_cpu)/slots
                    memory = min(free_memory, share_memory)
                    cpu = min(free_cpu, share_cpu if kind == 'worker' else min(2, share_cpu))
                    if exact is not None:
                        memory, cpu = exact['memory_mib'], exact['cpus']
                    minimum = share_memory if kind=='worker' and exact is None else min(512, ceiling)
                    if self.elastic:
                        share_cpu=(total['cpus']-sum(v['cpus'] for v in used if v['kind'] in ('terminal','control')))/(len(heavy)+1)
                        if len(heavy)<slots and memory>=minimum and memory<=free_memory:
                            self._rebalance_locked(pending_heavy=1) if exact is None else self._rebalance_locked(extra_cpu=cpu)
                        free_cpu=total['cpus']-sum(v['cpus'] for v in self.leases.values())
                        if exact is None:cpu=min(free_cpu,share_cpu)
                    available = len(heavy)<slots and memory >= minimum and cpu >= (math.floor(share_cpu*1000)/1000 if kind=='worker' and exact is None else min(.25, total['cpus'] - console_cpu)) and memory <= free_memory and cpu <= free_cpu
                if available:
                    value = {**total, 'memory_mib': memory, 'cpus': math.floor(cpu * 1000) / 1000,
                             'tmp_mib': min(1024, max(32, memory // 4)), 'threads': max(1, math.ceil(cpu))}
                    self.leases[owner] = {**value, 'kind': kind}
                    return value
                if deadline is not None and time.monotonic() >= deadline:
                    raise BudgetBusy('Budget risorse occupato; riprova dopo la chiusura della sessione')
                self.condition.wait(.25)

    def release(self, owner):
        with self.condition:
            if self.leases.pop(owner, None) is None:return
            if self.elastic:self._rebalance_locked()
            self.condition.notify_all()

    def quarantine(self, reason):
        with self.condition:
            self.blocked = reason
            self.condition.notify_all()


BUDGET = ResourceBudget(elastic=True)
