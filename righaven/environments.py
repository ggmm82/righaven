"""Native Agent/Skill definitions with small, separate deployment preferences."""
import hashlib
import json
from pathlib import Path
import re

from .state import atomic_json, applications

MODES = {'on_demand', 'preload'}
PRESETS = [
    {'id':'base','name':'Base: documenti e schemi','purpose':'Produrre testi, documenti e diagrammi modificabili con un insieme piccolo di strumenti. Python e Node sono sempre nel core; aggiungere solo le capacità necessarie.','tools':['pandoc','d2']},
    {'id':'documenti','name':'Documentale','purpose':'Scrivere, impaginare e revisionare documenti, libri e presentazioni con sorgenti modificabili e consegna portabile.','tools':['wordcraft','pdfcraft','deckcraft','pandoc','typst','calibre','epubcheck']},
    {'id':'progettazione','name':'Progettazione','purpose':'Trasformare idee in modelli, diagrammi e specifiche verificabili. Scegliere la notazione adatta e conservare i sorgenti editabili.','tools':['d2','plantuml','mermaid','excalidraw','bpmn','structurizr','typst']},
    {'id':'modellazione-3d','name':'3D e CAD','purpose':'Progettare geometrie e modelli 3D. Distinguere CAD parametrico, mesh e rendering; verificare i sorgenti nelle applicazioni native.','tools':['freecad','cadcraft','blender','ifcopenshell','pymeshlab']},
    {'id':'grafica','name':'Grafica','purpose':'Creare immagini, grafica vettoriale e composizioni modificabili, rispettando la tecnica scelta dall’utente.','tools':['photocraft','lightcraft','vectorcraft','designcraft','figcraft','excalidraw']},
    {'id':'web','name':'Web e interfacce','purpose':'Progettare e realizzare interfacce web, verificandone realmente comportamento, responsive e accessibilità pertinente al brief.','tools':['playwright','figcraft','vectorcraft']},
    {'id':'sviluppo','name':'Sviluppo software','purpose':'Realizzare software con sorgenti, dipendenze dichiarate, test eseguiti e istruzioni di avvio. Python e Node sono nel core; scegliere i tool del progetto senza duplicare framework.','tools':['playwright','d2']},
    {'id':'sicurezza','name':'Sicurezza e collaudo','purpose':'Verificare codice, dipendenze e applicazioni nei target autorizzati. Distinguere problemi confermati, sospetti e limiti dei controlli; consegnare evidenze e correzioni ripetibili.','tools':['opengrep','trivy','playwright']},
    {'id':'audio-video','name':'Audio, video e animazione','purpose':'Realizzare prodotti audiovisivi sincronizzati, conservando progetti nativi, media e sorgenti delle componenti.','tools':['soundcraft','filmcraft','effectcraft','ffmpeg','musescore','fluidsynth','aubio','whisper','opentimelineio','manim']},
    {'id':'dati','name':'Dati e analisi','purpose':'Analizzare dati e verificare calcoli e ipotesi, consegnando dataset pertinenti, formule o script e risultati riproducibili.','tools':['gridcraft','typst','d2']},
]
CORE_SKILLS = ('skill-harness', 'skill-workspace')
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')


def preferences_path(user_id):
    from righaven_core.config.paths import get_paths
    root = get_paths().user_dir(user_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'righaven-environments.json'
    if path.is_symlink():
        raise ValueError('Preferenze ambienti non valide')
    return path


def preferences(user_id):
    path = preferences_path(user_id)
    if not path.exists():
        return {}
    if path.stat().st_size > 200000:
        raise ValueError('Preferenze ambienti troppo grandi')
    value = json.loads(path.read_text())
    return value if isinstance(value, dict) else {}


def set_deployment(user_id, name, mode, ephemeral=False, preload_tools=None, tool_versions=None):
    if not NAME.fullmatch(name) or mode not in MODES or type(ephemeral) is not bool:
        raise ValueError('Configurazione di deploy non valida')
    if mode == 'preload' and ephemeral:
        raise ValueError('Un ambiente precaricato deve restare nella cache')
    from .tool_versions import check_selection
    versions=check_selection(tool_versions or {})
    known={a['id'] for a in applications()}
    if preload_tools is not None and (not isinstance(preload_tools,list) or len(preload_tools)>64 or any(t not in known for t in preload_tools)):
        raise ValueError('Strumenti da precaricare non validi')
    from .state import LOCK
    with LOCK:
        value = preferences(user_id)
        value[name] = {'mode':mode, 'ephemeral':ephemeral, 'preload_tools':sorted(set(preload_tools)) if preload_tools is not None else None,'tool_versions':versions}
        atomic_json(preferences_path(user_id), value)
    return value[name]


def skill_inventory(user_id):
    from righaven_core.skills.storage import get_or_new_user_skill_storage
    from .capability_policy import native_policy
    native_policy(user_id)  # Apply the existing one-time migration, never re-enable a skill.
    return get_or_new_user_skill_storage(user_id).load_skills(enabled_only=False)


def skill_requirements(skill):
    known = {a['id'] for a in applications()}
    tool = skill.name.removeprefix('skill-')
    if tool in known:
        return required_tools([tool])
    # Optional declarative dependencies for personal skills. No script execution.
    source = Path(skill.skill_dir) / 'SKILL.md'
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 200000:
        raise ValueError('Metadati skill non disponibili')
    text = source.read_text()
    frontmatter = re.match(r'^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)',text,re.DOTALL)
    if not frontmatter:return []
    import yaml
    try:metadata = yaml.safe_load(frontmatter.group(1)) or {}
    except yaml.YAMLError as exc:raise ValueError('Metadati della skill non validi') from exc
    if not isinstance(metadata,dict):raise ValueError('Frontmatter della skill non valido')
    extension = metadata.get('metadata') or {}
    if not isinstance(extension,dict):extension={}
    # The nested declaration passes RigHaven's native installer/validator.
    required = extension.get('righaven-tools',metadata.get('righaven-tools',[]))
    if not isinstance(required, list) or len(required)>40 or any(not isinstance(t,str) or t not in known for t in required):
        raise ValueError('righaven-tools deve elencare strumenti del catalogo')
    return required_tools(required)


def required_tools(explicit):
    from .environment_runtime import closure
    # Shared Chromium serves renderers without granting browser automation.
    return [tool for tool in closure(explicit) if tool!='playwright' or tool in explicit]


def resolve_skills(user_id, names):
    inventory = {s.name:s for s in skill_inventory(user_id)}
    if names is None:
        names = [s.name for s in inventory.values() if s.enabled]
    if not isinstance(names,list) or len(names)>200 or any(n not in inventory for n in names):
        raise ValueError('Seleziona skill native disponibili nel tuo account')
    selected = list(dict.fromkeys([*CORE_SKILLS,*names]))
    tools, disabled, extra = set(), [], []
    for name in selected:
        skill = inventory.get(name)
        if skill is None:
            if name in CORE_SKILLS:
                continue
            raise ValueError('Skill non disponibile: '+name)
        if not skill.enabled:
            disabled.append(name)
            continue
        required = skill_requirements(skill)
        for tool in required:
            dependency = inventory.get('skill-'+tool)
            if dependency is None or not dependency.enabled:
                raise ValueError('La skill '+name+' richiede uno strumento disabilitato: '+tool)
            tools.add(tool)
            extra.append(dependency.name)
    # Scope retains explicitly selected disabled skills, but cannot execute them.
    return {'skills':list(dict.fromkeys([*selected,*extra])), 'tools':sorted(tools), 'disabled':disabled}


def preset_catalog():
    known = {a['id'] for a in applications()}
    return [{**p, 'skills':[*CORE_SKILLS,'skill-problem-solving','skill-quality-review',*['skill-'+t for t in p['tools'] if t in known]],
             'missing_tools':[t for t in p['tools'] if t not in known]} for p in PRESETS]


def agent_instructions(user_id, agent):
    # HTTP AgentResponse embeds SOUL.md; native AgentConfig deliberately does
    # not. Startup loads configs and must use the owner-scoped native store.
    if hasattr(agent, 'soul'):
        return agent.soul or ''
    from righaven_core.config.agents_config import load_agent_soul
    return load_agent_soul(agent.name, user_id=user_id) or ''


def profile(user_id, agent):
    resolved = resolve_skills(user_id, agent.skills)
    prefs = preferences(user_id).get(agent.name, {'mode':'on_demand','ephemeral':False})
    identity = {'name':agent.name, 'purpose':agent.description, 'instructions':agent_instructions(user_id,agent), 'skills':resolved['skills']}
    return {**identity, 'tools':resolved['tools'], 'disabled':resolved['disabled'],
            'display_name':agent.display_name or agent.name, 'deployment':prefs,
            'revision':hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()}


def preloaded_tools(prefs, allowed):
    if prefs.get('mode')!='preload':return []
    selected=prefs.get('preload_tools')
    return sorted(set(allowed) & set(allowed if selected is None else selected))
