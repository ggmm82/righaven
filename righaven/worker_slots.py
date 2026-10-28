"""FIFO admission uses these slots; account refresh has its own exclusive lock."""
from contextlib import contextmanager
from datetime import datetime, timezone
import threading
import time


class WorkerSlots:
    def __init__(self):
        self.condition=threading.Condition();self.owners={};self.blocked=''

    def capacity(self):
        from .runtime_settings import effective
        value=effective();console=min(256,value['memory_mib']//4)+min(512,value['memory_mib']//4)
        return max(1,min(value.get('max_workers',2),(value['memory_mib']-console)//512,
                         int((value['cpus']-min(.25,value['cpus']/4)-min(.5,value['cpus']/4))/.25)))

    @contextmanager
    def foreground_request(self):yield

    def acquire(self,blocking=True,timeout=-1):
        deadline=None if timeout<0 else time.monotonic()+timeout
        with self.condition:
            while self.blocked or len(self.owners)>=self.capacity():
                if not blocking:return False
                remaining=None if deadline is None else deadline-time.monotonic()
                if remaining is not None and remaining<=0:return False
                self.condition.wait(.25 if remaining is None else min(.25,remaining))
            identity=threading.get_ident()
            if identity in self.owners:raise RuntimeError('Incarico già ammesso su questo thread')
            self.owners[identity]=datetime.now(timezone.utc).isoformat();return True

    def release(self):
        with self.condition:
            if self.owners.pop(threading.get_ident(),None) is None:raise RuntimeError('Slot non posseduto')
            self.condition.notify_all()

    def quarantine(self,reason):
        with self.condition:self.blocked=reason;self.condition.notify_all()

    def locked(self):
        with self.condition:return bool(self.owners or self.blocked)

    def waiting_info(self):
        with self.condition:
            return {'queue_reason':'cleanup' if self.blocked else 'workers',
                'queue_activity_since':min(self.owners.values(),default=''),
                'queue_detail':self.blocked or f'{len(self.owners)} incarichi attivi; limite {self.capacity()}. Attendo un posto disponibile.'}


WORKERS=WorkerSlots()
