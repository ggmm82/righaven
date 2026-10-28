"""One bounded execution slot; interactive requests preempt optional preparation.

Preemption is a request, never an early release: the preparer must first remove
its container. Verified image caches survive; unfinished installations retry.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import threading
import time


class ResourceSlot:
    def __init__(self, idle_seconds=10):
        self.condition=threading.Condition()
        self.owner=None
        self.foreground_waiters=0
        self.last_foreground=float('-inf')
        self.idle_seconds=idle_seconds
        self.blocked=''

    def _request_priority(self):
        if self.owner and self.owner['kind']=='preload':self.owner['yield'].set()
        self.condition.notify_all()

    @contextmanager
    def foreground_request(self):
        with self.condition:
            self.foreground_waiters+=1
            self._request_priority()
        try:yield
        finally:
            with self.condition:
                self.foreground_waiters-=1
                self.last_foreground=time.monotonic()
                self.condition.notify_all()

    def acquire(self, blocking=True, timeout=-1):
        until=None if timeout<0 else time.monotonic()+timeout
        with self.foreground_request():
            with self.condition:
                while self.owner or self.blocked:
                    if not blocking:return False
                    remaining=None if until is None else until-time.monotonic()
                    if remaining is not None and remaining<=0:return False
                    self.condition.wait(remaining)
                self.owner={'kind':'work','since':datetime.now(timezone.utc).isoformat()}
                return True

    def acquire_background(self,cancel,yield_event):
        with self.condition:
            while True:
                if cancel.is_set():return False
                idle=time.monotonic()-self.last_foreground>=self.idle_seconds
                if not self.owner and not self.blocked and not self.foreground_waiters and idle:
                    self.owner={'kind':'preload','since':datetime.now(timezone.utc).isoformat(),'yield':yield_event}
                    return True
                self.condition.wait(.1)

    def acquire_terminal(self, timeout=15):
        """Yield optional preparation, but never queue ahead of foreground chats."""
        until=time.monotonic()+timeout
        with self.condition:
            if self.blocked or self.foreground_waiters or self.owner and self.owner['kind']!='preload':
                return False
            with self.foreground_request():
                while self.owner:
                    if self.blocked or self.foreground_waiters>1 or self.owner['kind']!='preload':return False
                    remaining=until-time.monotonic()
                    if remaining<=0:return False
                    self.condition.wait(remaining)
                if self.blocked or self.foreground_waiters>1:return False
                self.owner={'kind':'terminal','since':datetime.now(timezone.utc).isoformat()}
                return True

    def acquire_maintenance(self):
        # A cache eviction request must not interrupt a compiler merely to
        # return HTTP 409. Only execution/login demand asks a preload to yield.
        with self.condition:
            if self.owner or self.blocked or self.foreground_waiters:return False
            self.owner={'kind':'maintenance','since':datetime.now(timezone.utc).isoformat()}
            return True

    def release(self):
        with self.condition:
            if self.owner is None:raise RuntimeError('release unlocked resource slot')
            if self.owner['kind'] in ('work','terminal'):self.last_foreground=time.monotonic()
            self.owner=None
            self.condition.notify_all()

    def quarantine(self,reason):
        with self.condition:
            self.blocked=reason
            self.condition.notify_all()

    def locked(self):
        with self.condition:return self.owner is not None or bool(self.blocked)

    def waiting_info(self):
        with self.condition:
            if self.blocked:return {'queue_reason':'cleanup','queue_activity_since':'','queue_detail':self.blocked}
            if self.owner and self.owner['kind']=='preload':
                return {'queue_reason':'preload','queue_activity_since':self.owner['since'],
                    'queue_detail':'Il precaricamento sta liberando le risorse per questa chat.'}
            if self.owner and self.owner['kind']=='terminal':
                return {'queue_reason':'terminal','queue_activity_since':self.owner['since'],
                    'queue_detail':'Un terminale web sta usando lo slot della squadra. Chiudilo per liberare le risorse.'}
            return {'queue_reason':'work','queue_activity_since':(self.owner or {}).get('since',''),
                    'queue_detail':'Le risorse sono occupate da un altro incarico.'}

    def __enter__(self):self.acquire();return self
    def __exit__(self,*args):self.release()


class PreparationCancel:
    def __init__(self,cancel,yield_event):self.cancel=cancel;self.yield_event=yield_event
    def is_set(self):return self.cancel.is_set() or self.yield_event.is_set()
    @property
    def deferred(self):return self.yield_event.is_set() and not self.cancel.is_set()
