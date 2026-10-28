"""User-facing preparation records survive polling/restarts independently of images."""
import hashlib
import json
from pathlib import Path
import re
import time
from . import state
from .progress import clean_summary

ACTIVE={'resolving_versions','checking_versions','queued','waiting_chat','installing','adapters','checking','publishing','preparing'}
LABELS={'resolving_versions':'Ricerca delle versioni','checking_versions':'Verifica delle versioni',
    'queued':'In attesa di risorse','waiting_chat':'In attesa della chat','installing':'Installazione dei programmi',
    'adapters':'Configurazione degli strumenti','checking':'Collaudo dell’ambiente','preparing':'Preparazione dell’ambiente',
    'publishing':'Salvataggio dell’immagine software','ready':'Programmi pronti','failed':'Preparazione non riuscita','cancelled':'Preparazione annullata','interrupted':'Preparazione interrotta'}


def path(user,name):
    key=hashlib.sha256((str(user)+'\0'+name).encode()).hexdigest()
    return state.STATE/'environment-preparations'/(key+'.json')


def read(user,name):
    file=path(user,name)
    if not file.exists():return {}
    if file.is_symlink() or file.stat().st_size>32000:raise ValueError('Registro preparazione non valido')
    return json.loads(file.read_text())


def update(user,name,**fields):
    with state.LOCK:
        value=read(user,name)
        changed={k:v for k,v in fields.items() if value.get(k)!=v}
        if changed:
            value.update(changed,updated_at=time.time());state.atomic_json(path(user,name),value)
        return value


def begin(user,name,selection):
    previous=read(user,name)
    value={'phase':'resolving_versions','started_at':time.time(),'updated_at':time.time(),
        'selection':selection,'tool':'','index':0,'total':len(selection),'error':'','environment_id':'',
        'previous_ready_id':previous.get('ready_id') or previous.get('previous_ready_id','')}
    state.atomic_json(path(user,name),value)
    return value


def diagnosis(text,error='',*,phase=''):
    """Report observed failures, never invent OOM from a generic exit code."""
    lines=text.splitlines();failed=[re.sub(r'^FAIL\s+','',line).split(' ',1)[0] for line in lines if line.startswith('FAIL ')]
    passed=[line.split(' ',2)[1] for line in lines if re.match(r'^OK [a-z0-9-]+(?:\s|$)',line) and 'cli' not in line.split(' ',2)[1] and line.split(' ',2)[1] not in ('env','craft')]
    installations=re.findall(r'^Installazione ([a-z0-9-]+) ',text,re.M)
    tool=failed[0] if failed else installations[-1] if installations else ''
    detail=clean_summary('\n'.join(lines[-30:]),6000)
    observed=(text+'\n'+str(error)).lower()
    if phase=='publishing':
        tool='';kind='publication'
        message='Collaudi superati, ma la finalizzazione dell’ambiente non è stata completata.'
        action='Riprova la preparazione. Se si ripete, controlla il dettaglio Docker del salvataggio o del rilascio del container; non è un errore dello strumento.'
        detail=clean_summary(str(error)+'\n'+detail,6500)
    elif 'Atteso un eseguibile interno' in text:
        message=(tool+': ' if tool else '')+'impossibile individuare l’eseguibile nel pacchetto scaricato.'
        kind='package_layout';action='Riprova dopo l’aggiornamento dell’installatore oppure scegli una release precedente nelle opzioni avanzate dell’ambiente.'
    elif 'Segmentation fault' in text or 'exit 139' in text or 'exit -11' in text:
        message=(tool+': ' if tool else '')+'un processo dello strumento è andato in crash durante il collaudo.'
        if tool=='calibre':message='Calibre: il motore di esportazione PDF è andato in crash. Le altre verifiche completate restano registrate.'
        kind='native_crash';action='Riprova la preparazione. Se il crash si ripete, scegli un’altra release dello strumento nelle opzioni avanzate dell’ambiente.'
    elif 'Memoria insufficiente' in error or 'Memoria esaurita' in error:
        message='Memoria insufficiente durante la preparazione.';kind='memory';action='Attendi la fine degli altri lavori oppure aumenta il budget RAM in La tua squadra.'
    elif any(token in observed for token in ('temporary failure','could not resolve','connection timed out','http error 429','http error 502','http error 503')):
        message='Un download non è riuscito: il servizio remoto non era raggiungibile.';kind='network';action='Riprova la preparazione; le versioni già verificate restano conservate.'
    else:
        message=(tool+': collaudo non superato.' if tool else clean_summary(error,400)) or 'Preparazione non completata.'
        kind='verification';action='Apri i dettagli della preparazione per il controllo non superato; puoi riprovare o scegliere una versione precedente.'
    return {'kind':kind,'tool':tool,'message':message,'action':action,'details':detail,
        'passed_tools':sorted(set(passed)),'failed_tools':sorted(set(failed))}


def snapshot(user,name,runtime,active=False):
    value=read(user,name)
    if not value:return None
    phase=value.get('phase','')
    if value.get('environment_id')==runtime.get('id') and runtime.get('status') in ACTIVE|{'ready'}:
        phase=runtime['status']
    if phase in ACTIVE and not active:
        phase='interrupted'
    result={**value,'phase':phase,'label':LABELS.get(phase,phase),'active':active and phase in ACTIVE}
    if phase=='interrupted':result.update(error='La preparazione è stata interrotta. Puoi riprenderla senza cancellare la cache.')
    return result


def text(user,name):
    value=read(user,name)
    if not value:return ''
    lines=[LABELS.get(value.get('phase'),''),value.get('error','')]
    if value.get('tool'):lines.append('Strumento: '+value['tool']+' '+value.get('version',''))
    failure=value.get('failure') or {}
    if failure.get('action'):lines.append(failure['action'])
    if failure.get('details'):lines.append(failure['details'])
    return '\n'.join(line for line in lines if line)
