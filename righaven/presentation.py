"""Select real published products for a deterministic native file presentation."""
import hashlib,json
from .control_memory import project_view
from .projects import artifact_path,digest


def presentation(workspace,project,state):
    view=project_view(project or {}) or {};selected=(view.get('presentation') or {}).get('paths',[])
    records={f['path']:f for delivery in (project or {}).get('deliveries',[]) for f in delivery.get('files',[]) if isinstance(f,dict) and f.get('path')}
    paths=[];identities=[]
    for name in selected[:3]:
        path=artifact_path(workspace,name)
        if path is None:continue
        observed=digest(path);expected=records.get(name,{}).get('sha256')
        if expected and expected!=observed:continue
        paths.append(name);identities.append([name,observed])
    if not paths:return None
    signature=hashlib.sha256(json.dumps(identities).encode()).hexdigest()
    if signature==state.get('harness_presentation_signature'):return None
    if set(paths).issubset(set(state.get('artifacts') or [])):
        return {'signature':signature,'paths':[]}
    return {'signature':signature,'paths':paths,'status':(project or {}).get('status'),
            'note':'File disponibili per la verifica: i controlli aperti restano da completare.' if (project or {}).get('status')!='ready' else 'Risultato e sorgenti disponibili.'}
