"""Account-owned temporary CLI consoles; no project or provider credential mounts."""
import base64
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import termios
import threading
import time
import uuid

from . import state
from .terminal_text import TerminalText

SESSIONS={}
LOCK=threading.Lock()
CLIENT_LOCK=threading.Lock()
CLOSED_CLIENTS={}


class Session:
    def __init__(self,user,name,profile,policy,client_id=None):
        from .docker_runtime import TERMINAL_LOCK as EXECUTION_LOCK,base_arguments,runtime_arguments,mount,remove,host_path
        from .capability_policy import worker_arguments,stage_skills
        from .environment_runtime import read,image_exists,installation,recipe
        from .runtime_settings import effective
        self.client_id=client_id;self.user=user;self.profile=name;self.id=uuid.uuid4().hex;self.container='skill-terminal-'+self.id[:12]
        self.started=time.monotonic();self.last_seen=self.started;self.closed=False;self.text='';self.error='';self.returncode=None
        self.mutex=threading.Lock();self.condition=threading.Condition(self.mutex)
        self.raw=bytearray();self.raw_start=0;self.raw_end=0
        self.cancelled=threading.Event();self.decoder=TerminalText();self.resources=None
        self.environment_id=profile['runtime']['id'];record=read(self.environment_id)
        if record is None:
            base_key,spec=recipe([])
            if self.environment_id==base_key:record={'image_id':spec['core'],'base_only':True}
        if not record or not record.get('base_only') and not image_exists(record):raise ValueError('Prepara i programmi dell’ambiente prima di aprire il terminale')
        self.directory=state.STATE/'environment-terminals'/self.id
        self.directory.mkdir(parents=True)
        if not EXECUTION_LOCK.acquire_terminal(timeout=15):
            shutil.rmtree(self.directory,ignore_errors=True)
            reason=EXECUTION_LOCK.waiting_info()['queue_reason']
            messages={
                'preload':'Il precaricamento sta ancora liberando le risorse per il terminale. Riprova tra poco.',
                'terminal':'Limite dei terminali contemporanei raggiunto: chiudi una console oppure aumenta il parallelismo e il budget risorse.',
                'cleanup':'Il rilascio delle risorse non è confermato: controlla la sandbox prima di aprire il terminale.'}
            raise ValueError(messages.get(reason,'Un incarico o un collegamento account sta usando le risorse. Controlla i lavori sul server e attendi il termine prima di aprire il terminale.'))
        master=slave=None
        try:
            from .resource_budget import BUDGET
            self.resources=BUDGET.acquire(self.container,'terminal',timeout=15)
            master,slave=pty.openpty();self.fd=master
            fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',30,100,0,0))
            projection=self.directory/'skills';stage_skills(policy,profile['skills'],projection)
            for path in [projection,*projection.rglob('*')]:path.chmod(0o755 if path.is_dir() else 0o644)
            blocker=self.directory/'disabled';blocker.write_text('#!/bin/sh\necho "Strumento escluso da questo profilo" >&2\nexit 126\n');blocker.chmod(0o755)
            descriptor=self.directory/'job.json';state.atomic_json(descriptor,{'capability_policy':{'allowed':policy['allowed']}});descriptor.chmod(0o644)
            args=base_arguments(self.container,self.resources)+runtime_arguments()+worker_arguments(policy,host_path(blocker),projected_skills=True)+[
                '-it','--label','org.righaven.harness.installation='+installation(),
                '--label','org.righaven.environment='+self.environment_id,
                '--mount',mount(projection,'/mnt/skills/custom',True),'--mount',mount(descriptor,'/job.json',True),
                '--env','TERM=xterm-256color','--env','PS1=righaven$ ',record['image_id'],'bash','--noprofile','--norc','-i']
            self.process=subprocess.Popen(['docker',*args],stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
        except BaseException:
            if master is not None:os.close(master)
            try:remove(self.container)
            except RuntimeError as exc:
                EXECUTION_LOCK.quarantine(str(exc))
                from .resource_budget import BUDGET
                BUDGET.quarantine(str(exc))
                raise
            finally:
                shutil.rmtree(self.directory,ignore_errors=True)
                from .resource_budget import BUDGET
                BUDGET.release(self.container)
                EXECUTION_LOCK.release()
            raise
        finally:
            if slave is not None:os.close(slave)
        threading.Thread(target=self.read,daemon=True,name='environment-terminal').start()

    def read(self):
        from .docker_runtime import TERMINAL_LOCK as EXECUTION_LOCK,remove
        try:
            while True:
                if self.cancelled.is_set() or time.monotonic()-self.started>1800 or time.monotonic()-self.last_seen>60:break
                readable,_,_=select.select([self.fd],[],[],.25)
                if readable:
                    try:data=os.read(self.fd,8192)
                    except OSError:break
                    if not data:break
                    self.append_output(data)
                elif self.process.poll() is not None:break
        finally:
            confirmed=False
            try:
                remove(self.container);confirmed=True
                if self.process.poll() is None:
                    try:os.killpg(self.process.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                self.returncode=self.process.wait(timeout=10)
            except (OSError,RuntimeError,subprocess.SubprocessError):
                self.error='Chiusura del container non confermata: la squadra richiede un controllo'
                EXECUTION_LOCK.quarantine(self.error)
                from .resource_budget import BUDGET
                BUDGET.quarantine(self.error)
            finally:
                os.close(self.fd)
                if confirmed:
                    shutil.rmtree(self.directory,ignore_errors=True)
                    from .resource_budget import BUDGET
                    BUDGET.release(self.container)
                EXECUTION_LOCK.release()
                with self.condition:
                    self.closed=True;self.condition.notify_all()

    def append_output(self,data):
        with self.condition:
            self.text=(self.text+self.decoder.feed(data))[-64000:]
            self.raw.extend(data);self.raw_end+=len(data)
            if len(self.raw)>262144:
                extra=len(self.raw)-262144;del self.raw[:extra];self.raw_start+=extra
            self.condition.notify_all()

    def public(self,after=None,wait=0):
        self.last_seen=time.monotonic()
        with self.condition:
            if after is not None and after==self.raw_end and not self.closed and wait:
                self.condition.wait_for(lambda:self.raw_end!=after or self.closed,timeout=min(wait,1))
            result={'id':self.id,'profile':self.profile,'finished':self.closed,'closing':self.cancelled.is_set(),
                    'error':self.error,'returncode':self.returncode,'limits':self.resources}
            if after is None:result['text']=self.text
            else:
                reset=after<self.raw_start or after>self.raw_end
                start=self.raw_start if reset else after
                data=bytes(self.raw[start-self.raw_start:start-self.raw_start+65536])
                result.update(output_base64=base64.b64encode(data).decode(),cursor=start+len(data),
                              output_end=self.raw_end,reset=reset)
            return result

    def resize(self,cols,rows):
        if self.closed or self.cancelled.is_set():raise ValueError('Sessione terminata')
        if not 2<=cols<=1000 or not 2<=rows<=500:raise ValueError('Dimensioni del terminale non valide')
        self.last_seen=time.monotonic()
        try:
            fcntl.ioctl(self.fd,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0))
            # Docker's attached CLI forwards SIGWINCH through its native resize API.
            # There is no `docker container resize` CLI subcommand.
            os.kill(self.process.pid,signal.SIGWINCH)
        except (OSError,subprocess.SubprocessError) as exc:raise ValueError('Ridimensionamento del terminale non confermato') from exc

    def write(self,text):
        if self.closed or self.cancelled.is_set() or self.process.poll() is not None:raise ValueError('Sessione terminata')
        if len(text)>8192:raise ValueError('Input non valido')
        self.last_seen=time.monotonic()
        os.write(self.fd,text.encode())


def client_closed(user,client_id):
    if not client_id:return False
    with CLIENT_LOCK:
        now=time.monotonic()
        for key,when in list(CLOSED_CLIENTS.items()):
            if now-when>300:CLOSED_CLIENTS.pop(key,None)
        return (user,client_id) in CLOSED_CLIENTS


def close_client(user,client_id):
    # A page may disappear before its start response arrives. This tombstone
    # must be written without waiting on the constructor's global session lock.
    with CLIENT_LOCK:
        CLOSED_CLIENTS[(user,client_id)]=time.monotonic()
        while len(CLOSED_CLIENTS)>4096:CLOSED_CLIENTS.pop(next(iter(CLOSED_CLIENTS)))
    with LOCK:
        for session in SESSIONS.values():
            if session.user==user and getattr(session,'client_id',None)==client_id:session.cancelled.set()


def start(user,name,profile,policy,client_id=None):
    with LOCK:
        if client_closed(user,client_id):raise ValueError('La finestra del terminale è stata chiusa')
        for identifier,session in list(SESSIONS.items()):
            if session.closed and time.monotonic()-session.last_seen>300:SESSIONS.pop(identifier,None)
            elif session.user==user and session.profile==name and getattr(session,'client_id',None)==client_id and not session.closed and not session.cancelled.is_set():return session.public()
        session=Session(user,name,profile,policy,client_id=client_id)
        if client_closed(user,client_id):session.cancelled.set()
        SESSIONS[session.id]=session
        return session.public()


def get(user,identifier):
    session=SESSIONS.get(identifier)
    if not session or session.user!=user:raise FileNotFoundError()
    return session
