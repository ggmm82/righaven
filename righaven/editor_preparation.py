"""Optional editor interfaces belong to existing native environment profiles."""
import threading
import time
import uuid
from . import environments,editor_assets,editor_catalog,tool_versions
JOBS={}
LOCK=threading.RLock()


def options(user,name,tools):
    selected=environments.preferences(user).get(name,{}).get('editors',[]);rows=[]
    with LOCK:
        for row in editor_catalog.definitions():
            if row['tool'] not in tools:continue
            rows.append({'id':row['id'],'name':row['name'],'mode':row['mode'],'preload':row['id'] in selected,'integration':row['integration'],**JOBS.get((user,name,row['id']),{'state':'on_demand'})})
    return rows


def configure(user,name,selected,tools):
    possible={r['id'] for r in editor_catalog.definitions() if r['tool'] in tools}
    if not isinstance(selected,list) or len(selected)>24 or any(v not in possible for v in selected):raise ValueError('Select editors of enabled skills in this environment')
    from .state import LOCK,atomic_json
    with LOCK:
        prefs=environments.preferences(user);prefs.setdefault(name,{'mode':'on_demand','ephemeral':False})['editors']=sorted(set(selected))
        if prefs[name].get('source_pack'):prefs[name]['source_pack']={**prefs[name]['source_pack'],'modified':True}
        atomic_json(environments.preferences_path(user),prefs)
    schedule(user,name,tools);return options(user,name,tools)


def schedule(user,name,tools):
    possible={r['id'] for r in editor_catalog.definitions() if r['tool'] in tools}
    for identifier in environments.preferences(user).get(name,{}).get('editors',[]):
        if identifier not in possible:continue
        key=(user,name,identifier)
        with LOCK:
            if JOBS.get(key,{}).get('state')=='preparing':continue
            JOBS[key]={'state':'preparing','message':'Preparing selected editor'}
        threading.Thread(target=prepare,args=(user,name,identifier),daemon=True,name='editor-preload-'+identifier).start()


def prepare(user,name,identifier):
    key=(user,name,identifier);claim='editor-preload-'+uuid.uuid4().hex
    software=None;interface_id=None
    def progress(message):
        with LOCK:JOBS[key]={'state':'preparing','message':message}
    try:
        from .capability_policy import native_policy
        definition=editor_catalog.editor(identifier,native_policy(user,name)['allowed']);tool=definition['tool']
        pins=tool_versions.resolved(tool_versions.software_selections(user,name,[tool]),wait=True,refresh=False)
        app=tool_versions.packages(pins).get(tool,{}).get('app') or tool_versions.builtins()[tool]
        if definition['package']=='craft-web':
            editor_assets.request(identifier,app['version'])
            while True:
                status=editor_assets.status(identifier,app['version'])
                if status['state']=='ready':break
                if status['state']=='failed':raise ValueError(status['message'])
                progress(status.get('message','Preparing browser editor'));time.sleep(1)
        elif definition['package']!='builtin':
            from .environment_runtime import ensure
            from .editor_runtime import interface
            software=ensure([tool],versions=pins,claim=claim)
            tag=interface(software['image_id'],definition['package'],progress,claim=claim+'-interface');interface_id=tag.split(':',1)[1]
            from .state import LOCK as preferences_lock,atomic_json
            with preferences_lock:
                prefs=environments.preferences(user)
                if identifier in prefs.get(name,{}).get('editors',[]):
                    prefs[name].setdefault('editor_software',{})[identifier]={'environment_id':software['id'],'interface_id':interface_id}
                    atomic_json(environments.preferences_path(user),prefs)
        with LOCK:JOBS[key]={'state':'ready','message':'Interactive software ready; no editing process running','version':app['version']}
    except Exception as error:
        with LOCK:JOBS[key]={'state':'failed','message':str(error)[:1000]}

    finally:
        from .environment_runtime import release_claim
        release_claim(claim);release_claim(claim+'-interface')
