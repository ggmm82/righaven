"""Editor software follows trusted assignment provenance, never a worker's claims."""
import json
from pathlib import Path
import re
from . import tool_versions
from .progress import JOB_ID


def _record(path,maximum=50000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>maximum:return None
    try:
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) else None
    except (OSError,ValueError):return None


def selection(workspace,original,definition):
    tool=definition['tool']
    if not tool:return {'tool_versions':{},'editor_version':'builtin','cli_version':'builtin','version_origin':'builtin'}
    relative=Path(original).relative_to(Path(workspace).resolve());parts=relative.parts
    # A published revision retains the creating draft's immutable version choice.
    if len(parts)>3 and parts[:2]==('outputs','source-revisions') and re.fullmatch(r'[a-f0-9]{32}',parts[2]):
        saved=_record(Path(workspace)/'.righaven-project/editors'/parts[2]/'session.json',1000000)
        if saved and saved.get('editor')==definition['id']:
            from .source_packages import digest
            virtual='/mnt/user-data/'+relative.as_posix()
            if any(item.get('path')==virtual and item.get('sha256')==digest(original) for item in saved.get('publications',[])):
                return {**{k:saved[k] for k in ('tool_versions','editor_version','cli_version','source_environment_id') if k in saved},'version_origin':'source_revision'}
    if len(parts)>3 and parts[:2]==('outputs','workspace') and JOB_ID.fullmatch(parts[2]):
        from .assignment_environments import snapshot_path
        saved=_record(snapshot_path(workspace,parts[2]))
        if saved and tool in saved.get('tools',[]):
            pin=(saved.get('versions') or {}).get(tool,'builtin');pins={}
            if isinstance(pin,str) and re.fullmatch(r'[a-f0-9]{64}',pin):
                package=tool_versions.read(pin)
                if package and package.get('state')=='ready' and package['bundle']['app']['id']==tool:pins={tool:pin}
            from .environment_runtime import read
            environment=read(saved['environment_id']) if re.fullmatch(r'[a-f0-9]{64}',str(saved.get('environment_id',''))) else None
            version=(environment or {}).get('installed_versions',{}).get(tool) or (environment or {}).get('tool_version_names',{}).get(tool)
            if pins:version=tool_versions.packages(pins)[tool]['app']['version']
            if isinstance(version,str) and re.fullmatch(r'[0-9][0-9A-Za-z.+:~_-]{0,100}',version.removeprefix('v')):
                version=version.removeprefix('v')
                return {'tool_versions':pins,'editor_version':version,'cli_version':version,'version_origin':'source_assignment',**({'source_environment_id':environment['id']} if environment else {})}
    pins=tool_versions.resolved(tool_versions.software_selections(tools=[tool]),wait=True,refresh=False)
    app=tool_versions.packages(pins).get(tool,{}).get('app') or tool_versions.builtins()[tool]
    return {'tool_versions':pins,'editor_version':app['version'],'cli_version':app['version'],'version_origin':'default'}


def software(document,tool,owner,cancel,user=None):
    from .environment_runtime import read,image_exists,claim_environment,ensure
    tools=[tool];pins=document.get('tool_versions',{});profile=document.get('environment_profile')
    if user and profile:
        from righaven_core.config.agents_config import load_agent_config
        from .environments import resolve_skills
        from .capability_policy import native_policy,require_tools
        agent=load_agent_config(profile,user_id=user)
        if agent is None:raise ValueError('Editor environment not found; recover or select its configuration before reopening')
        tools=resolve_skills(user,agent.skills)['tools']
        policy=native_policy(user,profile);require_tools(policy,tools)
        if tool not in tools:raise ValueError('The editor environment no longer enables this tool; update its skills before reopening')
        selected=tool_versions.software_selections(user,profile,tools)
        # Other configured programs follow the environment. The application's
        # recorded source format must not migrate merely because defaults change.
        selected[tool]=pins.get(tool,'builtin')
        pins=tool_versions.resolved(selected,wait=True,refresh=False,cancel=cancel)
    source=document.get('runtime_environment_id') or document.get('source_environment_id')
    required=document.get('cli_version',document['editor_version']).removeprefix('v')
    if source:
        record=read(source)
        reusable=record and set(tools).issubset(record.get('tools',[])) and image_exists(record)
        if reusable and user and profile:
            packages=tool_versions.packages(pins);catalog=tool_versions.builtins()
            names=record.get('tool_version_names') or record.get('installed_versions') or {}
            for selected_tool in tools:
                expected=required if selected_tool==tool else (packages.get(selected_tool,{}).get('app') or catalog[selected_tool])['version'].removeprefix('v')
                observed=str(names.get(selected_tool,'')).removeprefix('v')
                if observed!=expected or selected_tool!=tool and record.get('versions',{}).get(selected_tool,'builtin')!=pins.get(selected_tool,'builtin'):
                    reusable=False;break
        if reusable:
            claimed=claim_environment(record,owner)
            return {**claimed,'editor_allowed_tools':tools} if user and profile else claimed
    app=tool_versions.packages(pins).get(tool,{}).get('app') or tool_versions.builtins()[tool]
    if required!=app['version'].removeprefix('v'):
        current=tool_versions.resolved(tool_versions.software_selections(tools=[tool]),wait=True,refresh=False,cancel=cancel)
        restored=tool_versions.packages(current).get(tool,{}).get('app') or tool_versions.builtins()[tool]
        if restored['version'].removeprefix('v')!=required:raise ValueError('Prepare the recorded editor version before reopening this draft')
        pins={**pins,**{tool:current[tool]} } if tool in current else {k:v for k,v in pins.items() if k!=tool}
    result=ensure(tools,versions=pins,claim=owner,cancel=cancel,**({'prefer':source} if user and profile and source else {}))
    return {**result,'editor_allowed_tools':tools} if user and profile else result

