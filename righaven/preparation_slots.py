"""Bounded parallel preparation; maintenance is exclusive and preloads yield safely."""
from contextlib import contextmanager
from datetime import datetime,timezone
import threading,time
from .worker_slots import WorkerSlots


class PreparationSlots(WorkerSlots):
    def __init__(self):
        super().__init__();self.foreground_waiters=0;self.maintenance=False

    def _yield_preloads(self):
        for owner in self.owners.values():
            if owner['kind']=='preload':owner['yield'].set()
        self.condition.notify_all()

    @contextmanager
    def foreground_request(self):
        with self.condition:self.foreground_waiters+=1;self._yield_preloads()
        try:yield
        finally:
            with self.condition:self.foreground_waiters-=1;self.condition.notify_all()

    def acquire(self,blocking=True,timeout=-1):
        deadline=None if timeout<0 else time.monotonic()+timeout
        with self.condition:
            self.foreground_waiters+=1
            try:
                while self.blocked or self.maintenance or len(self.owners)>=self.capacity():
                    if not blocking:return False
                    self._yield_preloads()
                    remaining=None if deadline is None else deadline-time.monotonic()
                    if remaining is not None and remaining<=0:return False
                    self.condition.wait(.1 if remaining is None else min(.1,remaining))
                identity=threading.get_ident()
                if identity in self.owners:raise RuntimeError('Preparazione già ammessa su questo thread')
                self.owners[identity]={'kind':'work','since':datetime.now(timezone.utc).isoformat()};return True
            finally:self.foreground_waiters-=1;self.condition.notify_all()

    def acquire_background(self,cancel,yield_event):
        with self.condition:
            while True:
                if cancel.is_set():return False
                if not self.blocked and not self.maintenance and not self.foreground_waiters and len(self.owners)<self.capacity():
                    identity=threading.get_ident()
                    if identity in self.owners:raise RuntimeError('Preparazione già ammessa su questo thread')
                    self.owners[identity]={'kind':'preload','since':datetime.now(timezone.utc).isoformat(),'yield':yield_event};return True
                self.condition.wait(.1)

    def acquire_maintenance(self):
        with self.condition:
            if self.blocked or self.owners or self.foreground_waiters or self.maintenance:return False
            self.maintenance=True;return True

    def release(self):
        with self.condition:
            if self.maintenance:self.maintenance=False
            elif self.owners.pop(threading.get_ident(),None) is None:raise RuntimeError('Slot preparazione non posseduto')
            self.condition.notify_all()

    def locked(self):
        with self.condition:return bool(self.owners or self.maintenance or self.blocked)

    def waiting_info(self):
        with self.condition:
            return {'queue_reason':'cleanup' if self.blocked else 'preparations',
                'queue_activity_since':min((v['since'] for v in self.owners.values()),default=''),
                'queue_detail':self.blocked or f'{len(self.owners)} preparazioni attive; limite {self.capacity()}.'}

    def __enter__(self):self.acquire();return self
    def __exit__(self,*args):self.release()


class TerminalSlots:
    """PTY cleanup runs on a different thread; sessions release one counted slot."""
    def __init__(self):self.condition=threading.Condition();self.active=0;self.blocked=''

    def acquire_terminal(self,timeout=15):
        from .resource_budget import console_capacity
        from .runtime_settings import effective
        deadline=time.monotonic()+timeout
        with self.condition:
            while self.blocked or self.active>=console_capacity(effective()):
                if self.blocked or time.monotonic()>=deadline:return False
                self.condition.wait(min(.1,max(0,deadline-time.monotonic())))
            self.active+=1;return True

    def release(self):
        with self.condition:
            if not self.active:raise RuntimeError('Slot terminale non posseduto')
            self.active-=1;self.condition.notify_all()

    def quarantine(self,reason):
        with self.condition:self.blocked=reason;self.condition.notify_all()

    def locked(self):
        with self.condition:return bool(self.active or self.blocked)

    def waiting_info(self):return {'queue_reason':'cleanup' if self.blocked else 'terminal','queue_activity_since':'','queue_detail':self.blocked or 'Limite dei terminali contemporanei raggiunto.'}
