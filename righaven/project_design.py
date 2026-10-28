"""Versioned design models and their explicit links to the current project."""
import hashlib
import json
from pathlib import Path
import re
from .projects import locked, load, workspace_path
from .state import atomic_json
from .progress import utcnow
from .design_models import APPS, EXTENSIONS, preflight

ID=re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')


def model_file(workspace, record):
    path=workspace_path(workspace,record['source_path'])
    root=Path(workspace).resolve()/'.righaven-project/designs'
    if not path or path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():raise ValueError('Sorgente della tavola non disponibile')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Il sorgente versionato è stato modificato fuori dal registro')
    return path


def bindings_for(project, rows):
    if not isinstance(rows,list) or len(rows)>200:raise ValueError('Collegamenti della tavola non validi')
    allowed={'step_id':{s['id'] for s in project.get('steps',[])},'role_id':{r['id'] for r in project.get('roles',[])},
             'criterion_id':{c['id'] for c in (project.get('acceptance') or {}).get('criteria',[])},
             'delivery_id':{(a.get('delivery_record') or {}).get('id') for s in project.get('steps',[]) for a in s.get('attempts',[])}}
    for row in rows:
        if not isinstance(row,dict) or set(row)-{'element_id',*allowed} or not isinstance(row.get('element_id'),str) or not 1<=len(row['element_id'])<=160:raise ValueError('ID elemento o collegamento non valido')
        if not any(k in row for k in allowed):raise ValueError('Collega l’elemento ad almeno una voce del progetto')
        for key in allowed:
            if key in row and row[key] not in allowed[key]:raise ValueError('Collegamento a una voce del progetto inesistente: '+key)
    return rows


def save_many(workspace, entries):
    with locked(workspace) as folder:
        project=load(folder,workspace)
        if not project or project.get('archived'):raise ValueError('Definisci prima il progetto attivo')
        records=project.setdefault('designs',[]);created=[];results=[]
        try:
            for item in entries:
                identifier,title,tool,text=item['identifier'],item['title'],item['tool'],item['text']
                expected_revision=item.get('expected_revision',0);actor=item.get('actor','team')
                if not isinstance(identifier,str) or not ID.fullmatch(identifier) or tool not in APPS:raise ValueError('Tavola o strumento non valido')
                if not isinstance(title,str) or not 1<=len(title.strip())<=140 or not isinstance(text,str) or not text.strip() or len(text.encode())>8*1024*1024:raise ValueError('Titolo o sorgente non valido')
                if type(expected_revision) is not int or expected_revision<0:raise ValueError('Revisione attesa non valida')
                old=next((d for d in records if d['id']==identifier),None);revision=old['revision'] if old else 0
                if revision!=expected_revision:raise ValueError('La tavola è cambiata: ricarica la revisione corrente prima di salvare')
                if old and old['tool']!=tool:raise ValueError('Conserva lo strumento della tavola; usa un nuovo ID per un’alternativa')
                if not old and len(records)>=12:raise ValueError('Massimo 12 tavole attive per progetto')
                linked=bindings_for(project,item.get('bindings') if item.get('bindings') is not None else (old or {}).get('bindings',[]))
                target=folder/'designs'/identifier/str(revision+1)/('model'+EXTENSIONS[tool])
                if not target.resolve().is_relative_to(folder.resolve()) or target.exists() or any(p.is_symlink() for p in target.parents if p.is_relative_to(folder)):raise ValueError('Percorso della revisione non valido')
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700);created.append(target);target.write_text(text);preflight(tool,target)
                record={'id':identifier,'title':title.strip(),'tool':tool,'revision':revision+1,'source_path':'/mnt/user-data/'+target.relative_to(Path(workspace).resolve()).as_posix(),
                        'sha256':hashlib.sha256(text.encode()).hexdigest(),'updated_at':utcnow(),'actor':actor,'state':'changed' if actor=='user' else 'proposed','bindings':linked}
                if item.get('preview_path'):
                    preview=workspace_path(workspace,item['preview_path'])
                    if not preview or preview.is_symlink() or not preview.is_file() or preview.suffix.lower() not in ('.png','.svg') or preview.stat().st_size>8*1024*1024:raise ValueError('Anteprima non valida')
                    import shutil
                    copied=target.with_name('preview'+preview.suffix.lower());created.append(copied);shutil.copy2(preview,copied)
                    record['preview_path']='/mnt/user-data/'+copied.relative_to(Path(workspace).resolve()).as_posix()
                if old:records[records.index(old)]=record
                else:records.append(record)
                results.append(record)
            project['updated_at']=utcnow();atomic_json(folder/'project.json',project)
            return results
        except Exception:
            for path in created:path.unlink(missing_ok=True)
            raise


def save(workspace, **item):
    return save_many(workspace,[item])[0]


def register(workspace, models, allowed):
    if not isinstance(models,list) or not 1<=len(models)<=12:raise ValueError('Specificare da 1 a 12 tavole')
    # Validate the batch before writing; model data never becomes a file path selector.
    prepared=[]
    for item in models:
        if not isinstance(item,dict) or set(item)-{'id','title','tool','source_path','bindings','expected_revision','preview_path'}:raise ValueError('Campi della tavola non validi')
        if item.get('tool') not in allowed:raise ValueError('Capacità di progettazione disabilitata')
        path=workspace_path(workspace,item.get('source_path',''))
        if not path or path.is_symlink() or not path.is_file() or path.stat().st_size>8*1024*1024:raise ValueError('Sorgente non disponibile nel progetto')
        relative=path.resolve().relative_to(Path(workspace).resolve())
        if relative.parts[0] not in ('outputs','uploads','workspace','.righaven-project'):raise ValueError('Usa un sorgente del progetto, non dati di configurazione')
        if path.suffix.lower()!=EXTENSIONS.get(item.get('tool')):raise ValueError('Estensione del sorgente non coerente con lo strumento')
        prepared.append((item,path.read_text()))
    return save_many(workspace,[{'identifier':i['id'],'title':i['title'],'tool':i['tool'],'text':text,'expected_revision':i.get('expected_revision',0),'bindings':i.get('bindings'),'actor':'team','preview_path':i.get('preview_path','')} for i,text in prepared])


def read(workspace, identifier):
    with locked(workspace) as folder:
        project=load(folder,workspace) or {}
        record=next((d for d in project.get('designs',[]) if d['id']==identifier),None)
        if not record:raise ValueError('Tavola non trovata')
        return {**record,'source':model_file(workspace,record).read_text()}
