"""Expiring browser activity, without pretending that a sandbox is running."""
import threading
import time

_LOCK=threading.Lock()
_SESSIONS={}
TTL=90


def update(user,thread,sid,profile,editor,client,active=True):
    key=(user,thread,sid,client)
    with _LOCK:
        now=time.monotonic()
        for old,row in list(_SESSIONS.items()):
            if row['expires']<=now:del _SESSIONS[old]
        if active and key not in _SESSIONS and sum(row['user']==user for row in _SESSIONS.values())>=256:
            raise ValueError('Too many active browser editor tabs')
        if not active:_SESSIONS.pop(key,None)
        else:_SESSIONS[key]={'user':user,'thread_id':thread,'editor_session':sid,'profile':profile,
            'role':'Editor · '+editor,'summary':'Browser editor open','phase':'editing',
            'observed_running':True,'browser':True,'expires':time.monotonic()+TTL}


def activity(user):
    with _LOCK:
        for key,row in list(_SESSIONS.items()):
            if row['expires']<=time.monotonic():del _SESSIONS[key]
        return [{k:v for k,v in row.items() if k not in ('user','expires')} for row in _SESSIONS.values() if row['user']==user]
