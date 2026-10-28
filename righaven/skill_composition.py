"""Compose project roles from authorized native skill packages, not professions."""
import hashlib
import json
from pathlib import Path
import re

NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')


def package_revision(directory,require_skill=True):
    root=Path(directory)
    if root.is_symlink() or not root.is_dir() or (require_skill and not (root/'SKILL.md').is_file()):raise ValueError('Pacchetto skill non disponibile')
    digest=hashlib.sha256();size=0;count=0
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Riferimento esterno nella skill')
        if path.is_dir():continue
        if not path.is_file():raise ValueError('File della skill non valido')
        size+=path.stat().st_size;count+=1
        if size>32*1024**2 or count>2000:raise ValueError('Pacchetto skill troppo grande')
        digest.update(path.relative_to(root).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def inventory(policy,query='',limit=12):
    from .environments import skill_requirements
    from .state import applications
    from types import SimpleNamespace
    import yaml
    tools={'skill-'+a['id']:a['id'] for a in applications()}
    result=[]
    for name,directory in sorted(policy.get('skill_sources',{}).items()):
        path=Path(directory)/'SKILL.md'
        if not NAME.fullmatch(name) or path.is_symlink() or not path.is_file() or path.stat().st_size>200000:continue
        text=path.read_text()
        front=re.match(r'^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)',text,re.DOTALL)
        try:metadata=yaml.safe_load(front.group(1)) if front else {}
        except yaml.YAMLError:continue
        if not isinstance(metadata,dict):continue
        description=str(metadata.get('description',''))[:600]
        if query and not all(word in (name+' '+description).casefold() for word in query.casefold().split()):continue
        try:required=skill_requirements(SimpleNamespace(name=name,skill_dir=directory));error=''
        except ValueError as exc:required=[];error=str(exc)
        result.append({'name':name,'description':description,'kind':'tool' if name in tools else 'protocol' if name in ('skill-harness','skill-workspace') else 'method',
                       'tools':required,'available':not error and set(required).issubset(policy['allowed']),
                       'issue':error or ('Strumento richiesto escluso dal profilo' if set(required)-set(policy['allowed']) else '')})
    result.sort(key=lambda item:({'method':0,'protocol':1,'tool':2}[item['kind']],item['name']))
    return {'skills':result[:limit],'total':len(result),'more':len(result)>limit}


def bind(spec,policy=None,previous=None):
    """Raw specifications retain user choices; resolved tools belong to the role."""
    if spec.get('composition_version')!=1:return spec
    names=spec.get('skills',[])
    bindings=[];required=set(spec['tools'])
    if policy is None:
        # Internal memory/lesson updates can preserve a previously compiled
        # composition, but cannot select a new package without native authority.
        old=(previous or {}).get('skill_bindings',[])
        if names!=[b['name'] for b in old]:raise ValueError('Seleziona le skill dal coordinatore con il profilo nativo')
        bindings=old
        for binding in old:required.update(binding['tools'])
    else:
        from .environments import skill_requirements
        from .capability_policy import require_tools
        from types import SimpleNamespace
        for name in names:
            if name=='skill-harness':raise ValueError('La skill di coordinamento resta al coordinatore; seleziona i metodi del ruolo')
            source=policy.get('skill_sources',{}).get(name)
            if not source or name not in policy.get('skill_names',[]):raise ValueError('Skill disabilitata o esclusa dal profilo: '+name)
            tools=skill_requirements(SimpleNamespace(name=name,skill_dir=source))
            require_tools(policy,tools);required.update(tools)
            bindings.append({'name':name,'revision':package_revision(source),'tools':tools})
    from .environments import required_tools
    resolved=required_tools(sorted(required))
    automatic=[]
    if policy is not None:
        from .capability_policy import require_tools
        require_tools(policy,resolved)
        for name in ['skill-workspace',*['skill-'+tool for tool in resolved]]:
            source=policy.get('skill_sources',{}).get(name)
            if name not in names and source and name in policy.get('skill_names',[]):
                automatic.append({'name':name,'revision':package_revision(source)})
    else:automatic=(previous or {}).get('package_bindings',[])
    return {**spec,'resolved_tools':resolved,'skill_bindings':bindings,'package_bindings':automatic}


def verify(role,policy):
    if not role or role.get('composition_version')!=1:return
    if role.get('skills',[])!=[b['name'] for b in role.get('skill_bindings',[])]:raise ValueError('Composizione delle skill incompleta: ricompila il ruolo')
    for binding in [*role.get('skill_bindings',[]),*role.get('package_bindings',[])]:
        source=policy.get('skill_sources',{}).get(binding['name'])
        if (binding['name'] not in policy.get('skill_names',[]) or not source
                or package_revision(source)!=binding['revision']):
            raise ValueError('Skill cambiata o disabilitata: ricompila il ruolo prima della delega')


def execution_skills(settings,role,policy):
    if role and role.get('composition_version')==1:
        verify(role,policy)
        names=['skill-workspace',*role.get('skills',[]),*['skill-'+t for t in role['tools']]]
    else:
        names=[s for s in settings['skills'] if s=='skill-workspace' or s.removeprefix('skill-') in policy['allowed']]
        if policy['source']=='righaven_core':names+=policy.get('extra_skills',[])
    return list(dict.fromkeys(s for s in names if policy['source']!='righaven_core' or s in policy['skill_names']))


def verify_projection(role,directory):
    for binding in [*(role or {}).get('skill_bindings',[]),*(role or {}).get('package_bindings',[])]:
        if package_revision(Path(directory)/binding['name'])!=binding['revision']:
            raise ValueError('Pacchetto skill cambiato durante la preparazione; ricompila il ruolo')


def execution_policy(role,policy,tools):
    if not role or role.get('composition_version')!=1:return policy
    from .state import applications
    from .capability_policy import require_tools
    require_tools(policy,tools)
    return {**policy,'allowed':sorted(tools),'blocked':sorted({a['id'] for a in applications()}-set(tools)),
            'available_on_request':sorted(set(policy['allowed'])-set(tools)),'execution_scope':'role'}


def verify_recovery(previous,current,role=None):
    if previous.get('execution_scope')=='role':
        from .capability_policy import require_tools
        require_tools(current,previous['allowed'])
        verify(role,current)
    elif set(previous['allowed'])!=set(current['allowed']):
        raise ValueError('Capacità cambiate durante la sessione')
