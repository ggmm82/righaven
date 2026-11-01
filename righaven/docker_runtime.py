"""The trusted Gateway controls RigHaven's private Docker daemon via its Unix socket."""
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .state import STATE, effective_agent, credential_dir, connection_status, custom_connection_path
from .progress import clean_summary, create_job, read_status, update, utcnow, workspace_key
from .work_results import failure_info, partial_files
from .execution_queue import QUEUE, recover_waiters
from .resource_slot import ResourceSlot
from .worker_slots import WORKERS
from .preparation_slots import PreparationSlots,TerminalSlots

IMAGE = os.getenv('RIGHAVEN_SANDBOX_IMAGE', 'righaven-sandbox:0.1.0')
EXECUTION_LOCK = ResourceSlot()
BUILD_LOCK = PreparationSlots()
TERMINAL_LOCK = TerminalSlots()
LABEL = 'org.righaven.harness.owner'
OWNER = os.getenv('HOSTNAME', 'harness')
_mounts = None


def internal_daemon():
    """Whether Docker belongs to RigHaven instead of the deployment host."""
    return os.getenv('RIGHAVEN_DOCKER_SCOPE', '').strip().lower() == 'internal'


def docker(*arguments, timeout=60):
    return subprocess.check_output(['docker', *arguments], text=True, timeout=timeout).strip()


def host_path(path):
    """Resolve a shared path in the daemon namespace.

    The internal daemon receives the two application volumes at the same paths
    as the Gateway.  No host path or outer Docker metadata is needed.
    """
    global _mounts
    path = Path(path).resolve()
    if internal_daemon():
        roots = [STATE.resolve(), Path(os.getenv('RIGHAVEN_HOME', '/mnt/user-data')).resolve()]
        if not any(path == root or path.is_relative_to(root) for root in roots):
            raise ValueError('Il percorso richiesto non appartiene ai dati condivisi con il runtime RigHaven')
        if ',' in str(path) or '\n' in str(path):
            raise ValueError('Percorso volume non valido')
        return str(path)
    if _mounts is None:
        _mounts = json.loads(docker('inspect', OWNER))[0]['Mounts']
    for mount in sorted(_mounts, key=lambda m: len(m['Destination']), reverse=True):
        destination = Path(mount['Destination'])
        if path.is_relative_to(destination):
            relative = path.relative_to(destination)
            candidate = Path(mount['Source']) / relative
            if ',' in str(candidate) or '\n' in str(candidate):
                raise ValueError('Percorso volume non valido')
            return str(candidate)
    raise ValueError('Il percorso richiesto non appartiene a un volume del Gateway')


def mount(path, target, read_only=False):
    value = f'type=bind,src={host_path(path)},dst={target}'
    return value + (',readonly' if read_only else '')


def worker_resources(name, *, cancel=None, timeout=120, exact=None, kind="worker"):
    from .resource_budget import BUDGET, BudgetBusy
    try:
        return BUDGET.acquire(name, kind, cancel=cancel, exact=exact, timeout=0)
    except BudgetBusy:
        # All foreground paths, including native recovery and account CLI
        # requests, ask optional builds to yield only under resource pressure.
        with BUILD_LOCK.foreground_request():
            return BUDGET.acquire(name, kind, cancel=cancel, exact=exact, timeout=timeout)


def base_arguments(name, resources=None):
    if resources is None:
        resources = worker_resources(name,kind='control')
    return ['run', '--name', name, '--label', f'{LABEL}={OWNER}',
            '--init', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--pids-limit=256', f"--memory={resources['memory_mib']}m", f"--memory-swap={resources['memory_mib']}m",
            f"--cpus={resources['cpus']}", '--network=bridge', '--tmpfs', f"/tmp:rw,size={resources['tmp_mib']}m",
            '--env', f"RIGHAVEN_CPU_THREADS={resources['threads']}",
            '--env', f"RIGHAVEN_MEMORY_MIB={resources['memory_mib']}",
            '--env', 'NO_BROWSER=true', '--env', 'TZ=Europe/Rome',
            '--env', f"TOKIO_WORKER_THREADS={resources['threads']}", '--env', f"RAYON_NUM_THREADS={resources['threads']}",
            '--env', f"OMP_NUM_THREADS={resources['threads']}", '--env', f"OPENBLAS_NUM_THREADS={resources['threads']}"]


def remove(name):
    try:
        result = subprocess.run(['docker', 'rm', '-f', name], capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        from .resource_budget import BUDGET
        BUDGET.quarantine('Rimozione sandbox non confermata')
        raise RuntimeError('Rimozione sandbox non confermata') from exc
    if result.returncode and 'No such container' not in result.stderr:
        # Do not admit another worker unless reclamation was confirmed.
        from .resource_budget import BUDGET
        BUDGET.quarantine('Rimozione sandbox non confermata')
        raise RuntimeError('Rimozione sandbox non confermata; riavvia il Gateway per recuperarla')
    from .resource_budget import BUDGET
    BUDGET.release(name)


def lifecycle(progress, **fields):
    # A telemetry write must never prevent container removal or lock release.
    try:
        update(progress, **fields)
    except (OSError, ValueError):
        pass


def cleanup_orphans():
    """A Gateway restart must reclaim workers left by its previous process."""
    ensure_software_image()
    # Scope to the persistent installation ID, not a shared daemon-wide prefix.
    installation = (STATE / 'installation-id').read_text().strip()
    ids = docker('ps', '-aq', '--filter', f'label=org.righaven.harness.installation={installation}')
    for container in ids.splitlines():
        remove(container)
    recover_waiters(STATE)


def ensure_software_image():
    """Make the verified worker base available in the application daemon."""
    inspected = subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True,
                               text=True, timeout=30)
    if inspected.returncode == 0:
        return
    pulled = subprocess.run(['docker', 'pull', IMAGE], capture_output=True, text=True,
                            timeout=1800)
    if pulled.returncode:
        detail = clean_summary(pulled.stderr or pulled.stdout or 'download non riuscito', 500)
        raise RuntimeError('Runtime RigHaven non disponibile: ' + detail)
    docker('image', 'inspect', IMAGE, timeout=30)


def runtime_arguments(*, skills=False):
    from .runtime_bundle import arguments
    return arguments(skills=skills)


def provider_image(engine,claim=None):
    from .tool_versions import selections,resolved
    chosen=selections(engine=engine)
    if not chosen:return IMAGE
    from .environment_runtime import ensure
    result=ensure([],versions=resolved(chosen,wait=True,refresh=False),claim=claim)
    return result.get('image_id') or result['image']


def close_provider(name):
    remove(name)
    from .environment_runtime import release_claim
    release_claim(name)


def generate_gemini(payload, timeout=1800):
    """No file tools or conversation volume in a coordinator generation container."""
    if not connection_status('gemini'):
        raise ValueError('Collega Antigravity nel pannello La tua squadra')
    if not EXECUTION_LOCK.acquire(timeout=120):
        raise RuntimeError('Squadra occupata; attendi il termine del lavoro attivo')
    name = 'rh-coordinator-' + uuid.uuid4().hex[:12]
    try:
        jobs = STATE / 'jobs'
        jobs.mkdir(exist_ok=True)
        job = jobs / (name + '.json')
        from .state import atomic_json
        atomic_json(job, payload)
        installation = (STATE / 'installation-id').read_text().strip()
        selected_image=provider_image('gemini',claim=name)
        args = base_arguments(name) + runtime_arguments() + ['--label', f'org.righaven.harness.installation={installation}',
            '--mount', mount(credential_dir('gemini'), '/credentials'),
            '--mount', mount(job, '/job.json', True),
            selected_image, 'python3', '/opt/righaven-worker/antigravity_cli.py', '/job.json']
        try:
            completed = subprocess.run(['docker', *args], capture_output=True, text=True,
                                       timeout=timeout + 60)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Timeout Antigravity: riprova dalla chat') from None
        try:
            result = json.loads(completed.stdout)
        except (ValueError, TypeError):
            raise RuntimeError('Risposta del coordinatore Antigravity non valida') from None
        if completed.returncode or result.get('ok') is not True:
            raise RuntimeError('Antigravity non disponibile: verifica account, quota e modello in La tua squadra')
        return result['response']
    finally:
        close_provider(name)
        if 'job' in locals():
            job.unlink(missing_ok=True)
        EXECUTION_LOCK.release()



def generate_claude(payload,timeout=1800):
    if not connection_status('claude'):raise ValueError('Connect Claude Code in Models & resources')
    if not EXECUTION_LOCK.acquire(timeout=120):raise RuntimeError('Provider credential session is busy; retry shortly')
    name='rh-claude-'+uuid.uuid4().hex[:12]
    try:
        jobs=STATE/'jobs';jobs.mkdir(exist_ok=True);job=jobs/(name+'.json')
        from .state import atomic_json
        atomic_json(job,payload)
        image=provider_image('claude',claim=name)
        args=base_arguments(name)+runtime_arguments()+['--mount',mount(credential_dir('claude'),'/credentials'),
             '--mount',mount(job,'/job.json',True),image,'python3','/opt/righaven-worker/claude_cli.py','/job.json']
        result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout+60)
        try:body=json.loads(result.stdout)
        except ValueError:raise RuntimeError('Invalid official Claude Code response') from None
        if result.returncode or body.get('ok') is not True:raise RuntimeError(body.get('error','Claude Code did not complete'))
        return body['response']
    finally:
        close_provider(name)
        if 'job' in locals():job.unlink(missing_ok=True)
        EXECUTION_LOCK.release()


def claude_models():
    # Official CLI aliases, not a fabricated account-specific model inventory.
    return [{'id':alias,'label':alias,'default':alias=='sonnet'} for alias in ('sonnet','opus','haiku')]

def antigravity_models():
    if not connection_status('gemini'):
        raise ValueError('Collega prima Antigravity con il tuo account Google')
    if not EXECUTION_LOCK.acquire(timeout=120):
        raise RuntimeError('Squadra occupata: riprova tra poco')
    name = 'rh-models-' + uuid.uuid4().hex[:12]
    try:
        installation = (STATE / 'installation-id').read_text().strip()
        selected_image=provider_image('gemini',claim=name)
        args = base_arguments(name) + runtime_arguments() + ['--label', f'org.righaven.harness.installation={installation}',
            '--mount', mount(credential_dir('gemini'), '/credentials'),
            selected_image, 'python3', '/opt/righaven-worker/antigravity_cli.py', '--models']
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=120)
        value = json.loads(result.stdout)
        if result.returncode or value.get('ok') is not True:
            raise RuntimeError('Ricollega Antigravity o verifica la disponibilità del tuo account Google')
        return value['models']
    finally:
        close_provider(name)
        EXECUTION_LOCK.release()


def codex_account(models=False, *, locked=False):
    if not locked and not EXECUTION_LOCK.acquire(timeout=120):
        raise RuntimeError('Squadra occupata: riprova tra poco')
    name = 'rh-refresh-' + uuid.uuid4().hex[:12]
    try:
        installation = (STATE / 'installation-id').read_text().strip()
        selected_image=provider_image('codex',claim=name)
        args = base_arguments(name) + runtime_arguments() + ['--label', f'org.righaven.harness.installation={installation}',
            '--mount', mount(credential_dir('codex'), '/root/.codex'),
            selected_image, 'python3', '/opt/righaven-worker/refresh_codex.py', *(['--models'] if models else [])]
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=90)
        if result.returncode or json.loads(result.stdout).get('ok') is not True:
            raise RuntimeError('Ricollega Codex in La tua squadra')
        return json.loads(result.stdout)
    finally:
        close_provider(name)
        if not locked:EXECUTION_LOCK.release()


def refresh_codex_credentials():
    codex_account()


def codex_models():
    return codex_account(models=True)['models']


def recover_saved(args, progress, workspace, output_dir, error, *, policy=None,role=None,staging=None,early=False):
    """Bounded native verification of saved files; never retries the AI session."""
    from .cancellation import requested, watch
    from .projects import assert_user_allows_work, read_project
    attention = failure_info(error)
    folder = staging.output if staging is not None else Path(workspace) / Path(output_dir).relative_to('/mnt/user-data')
    manifest = folder / 'handoff.json'
    if ((not early and attention['code'] not in ('provider_quota', 'work_limit')) or requested()
            or read_status(progress).get('cancel_requested') or manifest.is_symlink()
            or (not early and not manifest.is_file()) or (manifest.is_file() and manifest.stat().st_size > 100000)
            or (staging is None and not folder.resolve().is_relative_to(Path(workspace).resolve()))):
        return None
    assert_user_allows_work(read_project(workspace) or {},allow_delivery=early)
    if policy:
        from .capability_policy import native_policy, legacy_policy
        current = (native_policy(policy['user_id'], policy.get('agent_name'))
                   if policy.get('source') == 'righaven_core' else legacy_policy())
        from .skill_composition import verify_recovery
        try:verify_recovery(policy,current,role)
        except ValueError:
            update(progress, artifact_recovery={'status': 'not_verified', 'session_error': attention['code'],
                'detail': 'Capacità modificate durante la sessione: serve una verifica con le impostazioni correnti.'})
            return None
    name = args[args.index('--name') + 1]
    try:
        state = json.loads(docker('inspect', '--format', '{{json .State}}', name))
        if state.get('OOMKilled'):
            return None
        remove(name)  # Stop the entire process tree before inspecting its outputs.
        # Same image, policy, limits and workspace, but no provider credentials.
        verification = []
        i = 0
        while i < len(args):
            if args[i] == '--mount' and 'dst=/credentials' in args[i + 1]:
                i += 2
                continue
            verification.append(args[i]); i += 1
        verification[-1:-1] = ['--finalize-early' if early else '--finalize']
        from datetime import datetime, timedelta, timezone
        update(progress, 'checking', 'Verifico i file salvati senza richiamare il modello',
               execution_state='tool', execution_started_at=utcnow(), finished_at='', worker_exit_at='',
               deadline_at=(datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat(),
               artifact_recovery={'status': 'running', 'session_error': attention['code']})
        if staging is not None:
            worker_resources(name, exact=read_status(progress)['limits'], timeout=300)
        with watch(lambda: request_stop(workspace, name), lambda: lifecycle(progress, cancel_error=True)):
            completed = subprocess.run(['docker', *verification], capture_output=True, text=True, timeout=300)
        result = json.loads(completed.stdout)
        if completed.returncode or not isinstance(result, dict) or result.get('ok') is not True:
            raise ValueError(result.get('error', 'Controlli dei file salvati non superati') if isinstance(result, dict) else 'Risposta non valida')
        result['recovery'] = {'status': 'verified', 'session_error': attention['code'],
                              'message': 'File salvati recuperati con controlli nativi, senza nuova generazione.'}
        if not early:result['attention'] = attention
        if early:
            result['user_requested_delivery']=True
            result['response']='Chiusura richiesta: mostra i file disponibili e i loro limiti; non avviare altre attività.'
        if not early:result['response'] = 'Versione recuperata: controlli tecnici registrati; qualità da valutare separatamente.'
        update(progress, artifact_recovery=result['recovery'])
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        update(progress, artifact_recovery={'status': 'not_verified', 'session_error': attention['code'],
                                            'detail': clean_summary(exc, 1000)})
        return None


def publish_staged(staging, result, progress):
    from .progress import heartbeat
    update(progress, 'finalizing', 'Verifico e pubblico la consegna dal suo staging isolato',
           can_stop=False, deadline_at=None, execution_state='tool')
    with heartbeat(progress):
        return staging.publish(result)


def completed_result(result, workspace, progress, image=None):
    image = image or IMAGE
    result['runtime_image'] = image
    from .verification_cache import save as save_verifications
    try:
        save_verifications(STATE, workspace, image, result)
    except (OSError, ValueError):
        pass
    lifecycle(progress, worker_exit_at=utcnow())
    update(progress, 'completed')
    return json.dumps(result, ensure_ascii=False)


def release_prepared_environment(environment, ephemeral):
    if not ephemeral or not environment or not environment.get('tools'):
        return
    from .environment_runtime import evict
    try:evict(environment['id'])
    except (OSError,ValueError,subprocess.SubprocessError):pass  # Protected/shared/in-use images stay cached.


from .organization_limits import organization_job


@organization_job
def delegate(agent_id, task, workspace, tool_call_id=None, on_started=None, requirements=None, purpose='work', acceptance=None, role=None, capability_policy=None, policy_review=None):
    from .capability_policy import legacy_policy, native_policy, require_tools, worker_arguments
    policy = capability_policy or legacy_policy()
    if policy.get('source') == 'righaven_core':
        policy = native_policy(policy['user_id'], policy.get('agent_name'))
    require_tools(policy, [] if agent_id == 'workspace' else [agent_id])
    settings = effective_agent(agent_id)
    if not settings or (policy['source'] != 'righaven_core' and not settings['enabled']):
        raise ValueError('Specialista sconosciuto o disattivato')
    role_text = None
    if role:
        from .project_skills import load_compiled
        if agent_id != 'workspace' and agent_id not in role['tools']:
            raise ValueError('La CLI assegnata deve essere inclusa negli strumenti del ruolo')
        role_text = load_compiled(workspace, role)
        require_tools(policy, role['tools'])
        if role.get('request_hash') != (acceptance or {}).get('hash'):
            raise ValueError('Ricompila il ruolo per la richiesta corrente prima della delega')
        settings = {**settings, 'skills': list(dict.fromkeys([*settings['skills'], *['skill-' + t for t in role['tools']]]))}
    from .skill_composition import execution_skills,verify,verify_projection,execution_policy
    settings['skills']=execution_skills(settings,role,policy)
    engine = settings['engine']
    if not connection_status(engine, settings.get('connection_id')):
        raise ValueError(f'Collega {engine} nel pannello RigHaven prima di usare lo specialista')
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    name = 'rh-job-' + uuid.uuid4().hex[:12]
    runtime_image = IMAGE
    runtime_environment = None
    ephemeral_environment = False
    progress = create_job(workspace, name, agent_id, engine, settings['model'], tool_call_id)
    update(progress, environment_profile=policy.get('agent_name') or '')
    if role:
        update(progress, role_id=role['id'], role_title=role['title'], role_version=role['version'])
    output_dir = '/mnt/user-data/outputs/' + agent_id + '/' + name
    # At most one login or worker at a time: bounded RAM and serialized credential refresh.
    from .cancellation import requested, watch
    def cancelled_before_start():
        update(progress, 'failed', 'Interruzione della fase richiesta dall’utente', cancel_requested=True)
        return json.dumps({'ok': False, 'error': 'Interruzione della fase richiesta dall’utente; nessun nuovo container avviato.'})
    if not QUEUE.acquire(WORKERS, progress, STATE, requested):
        return cancelled_before_start()
    try:
        if requested():
            return cancelled_before_start()
        # A user may disable a tool while this job waits in the execution queue.
        if policy.get('source') == 'righaven_core':
            policy = native_policy(policy['user_id'], policy.get('agent_name'))
        else:
            policy = legacy_policy()
        require_tools(policy, ([agent_id] if agent_id != 'workspace' else []) + (role or {}).get('tools', []))
        settings['skills']=execution_skills(settings,role,policy)
        from .projects import assert_user_allows_work, read_project
        assert_user_allows_work(read_project(workspace) or {})
        update(progress, 'starting')
        from .task_staging import TaskStaging
        staging = TaskStaging(STATE, workspace, agent_id, name)
        staging.prepare()
        if on_started:
            on_started(output_dir)
        jobs = STATE / 'jobs'
        jobs.mkdir(exist_ok=True)
        job = jobs / (name + '.json')
        from .runtime_settings import effective
        resources = effective()
        update(progress, limits=resources, can_stop=True)
        from . import environment_runtime as environments
        if environments.enabled():
            from .progress import heartbeat
            selected = list((role or {}).get('tools', [])) or ([] if agent_id == 'workspace' else [agent_id])
            needed = environments.source_tools(workspace, task.split('\n\nPiano del coordinatore',1)[0], selected)
            needed = sorted(set(needed) & set(policy['allowed']))
            # Browser is a rendering implementation detail, not permission to automate sites.
            require_tools(policy, set(environments.closure(needed)) - {'playwright'})
            if policy.get('source') == 'righaven_core' and policy.get('agent_name'):
                from .environments import preferences
                deployment = preferences(policy['user_id']).get(policy['agent_name'], {})
                ephemeral_environment = deployment.get('ephemeral', False)
            from datetime import datetime, timedelta, timezone
            update(progress, 'preparing_environment', 'Preparo gli strumenti dell’incarico', started_at=utcnow(),
                   deadline_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                   execution_state='environment', environment_started_at=utcnow())
            with heartbeat(progress):
                from .tool_versions import software_selections
                from . import environment_selection as profiles_base
                chosen_versions=software_selections(policy.get('user_id'),policy.get('agent_name'),needed)
                # A ready owner profile covering these tools is reused or extended, not rebuilt.
                base_profile=profiles_base.choose(policy.get('user_id'),needed,policy,(role or {}).get('skills',[])) if policy.get('source') == 'righaven_core' else None
                chosen_versions=profiles_base.versions(chosen_versions,base_profile)
                runtime_environment = environments.ensure(needed, acquire=True, progress=progress, cache_dependencies=not ephemeral_environment, claim=name,versions=chosen_versions,prefer=(base_profile or {}).get('id'))
                profile_use=profiles_base.outcome(base_profile,runtime_environment)
                if profile_use['mode'] in ('reused','extended'):
                    environments.save(base_profile['id'],last_used=time.time())
                    profiles_base.record_use(policy['user_id'],base_profile['name'],(role or {}).get('title') or agent_id,profile_use['mode'])
            runtime_image = runtime_environment.get('image_id') or runtime_environment['image']
            # Installation can take minutes: a newer native disable/scope must win before AI starts.
            policy = native_policy(policy['user_id'], policy.get('agent_name')) if policy.get('source') == 'righaven_core' else legacy_policy()
            verify(role,policy)
            require_tools(policy, selected)
            require_tools(policy, set(environments.closure(needed)) - {'playwright'})
            from .environments import required_tools
            settings['skills'] = list(dict.fromkeys([*settings['skills'], *['skill-'+t for t in required_tools(needed)]]))
            if policy.get('source') == 'righaven_core':
                settings['skills'] = [s for s in settings['skills'] if s in policy['skill_names']]
            update(progress, 'starting', environment_finished_at=utcnow(), environment={
                'id':runtime_environment['id'],'tools':runtime_environment['tools'],'assigned_tools':needed,'status':'ready','versions':runtime_environment.get('version_names',{}),
                'profile':profile_use})
        from .provider_bundle import prepare as prepare_provider,arguments as provider_arguments
        provider=prepare_provider(engine,policy.get('user_id'),policy.get('agent_name')) if environments.enabled() else None
        if provider:
            cli=provider[1]
            if runtime_environment is not None:
                runtime_environment={**runtime_environment,'version_names':{k:v for k,v in runtime_environment.get('version_names',{}).items() if not k.startswith('provider-')}}
                runtime_environment['version_names']['provider-'+cli['binary']]=cli['version']
            update(progress,provider_cli={'binary':cli['binary'],'version':cli['version'],'bundle':cli['id']})
            if runtime_environment is not None:
                update(progress,environment={'id':runtime_environment['id'],'tools':runtime_environment['tools'],'assigned_tools':needed,'status':'ready','versions':runtime_environment['version_names'],'profile':profile_use})
        if role and role.get('composition_version')==1:
            from .environments import required_tools
            task_tools=required_tools(needed) if runtime_environment is not None else role['tools']
            policy=execution_policy(role,policy,task_tools)
        credentials=None
        if engine in ('codex','gemini','claude'):
            from .credential_sessions import CredentialSession
            credentials=CredentialSession(engine,jobs/(name+'-credentials'))
        elif os.getenv('RIGHAVEN_EDITION', 'community') == 'cloud':
            from .credential_sessions import ApiCredentialSession
            credentials=ApiCredentialSession(engine,jobs/(name+'-credentials'),settings.get('connection_id'))
        from .connections import Delivery as ConnectionDelivery
        # Only the connections the role declares and the user assigned to this project; deleted with the worker.
        connections=ConnectionDelivery(workspace,role,jobs/(name+'-connections'))
        from .resource_budget import BUDGET
        from .cancellation import requested
        class CancelBudget:
            def is_set(self):
                return requested() or read_status(progress).get('cancel_requested', False) or read_status(progress).get('finish_requested', False)
        from .progress import heartbeat
        update(progress, 'preparing', 'Attendo le risorse per avviare l’incarico', execution_state='resources')
        with heartbeat(progress):
            resources = worker_resources(name, cancel=CancelBudget(), timeout=None)
        BUDGET.observe_progress(name,progress)
        if requested() or read_status(progress).get('cancel_requested') or read_status(progress).get('finish_requested'):
            return cancelled_before_start()
        update(progress, execution_state='launching')
        update(progress, limits=resources)
        payload = {'resources': resources, 'agent': agent_id, 'engine': engine, 'model': settings['model'],
                   'runtime_image': runtime_image,'tool_versions':(runtime_environment or {}).get('version_names',{}),
                   'instructions': settings['instructions'], 'skills': settings['skills'], 'task': task,
                   'run_id': name, 'timeout': 1500, 'requirements': requirements or {}, 'purpose': purpose,
                   'acceptance': acceptance, 'role': role, 'compiled_skill': role_text}
        if policy_review:
            if purpose != 'review':
                raise ValueError('Il contratto di una policy sheet si verifica soltanto in revisione')
            payload['policy_review'] = policy_review
        from .projects import read_project
        payload['user_direction'] = (read_project(workspace) or {}).get('user_direction')
        if connections.public:payload['connections'] = connections.public
        payload['capability_policy'] = dict(policy)
        if runtime_environment is not None:
            installed = sorted(set(runtime_environment['tools']) & set(policy['allowed']))
            payload['capability_policy'].update(installed=installed, available_on_request=sorted(set(payload['capability_policy'].get('available_on_request',[])) | (set(policy['allowed'])-set(installed))))
        from .verification_cache import load as load_verifications
        try:
            payload['verified_archives'] = load_verifications(STATE, workspace, runtime_image)
        except (OSError, ValueError):
            payload['verified_archives'] = {}
        if engine == 'deepseek' and not payload['model']:
            import yaml
            config = yaml.safe_load((STATE / 'config.yaml').read_text())
            payload['model'] = next(m['model'] for m in config['models'] if m['use'] == 'righaven.deepseek_provider:HarnessDeepSeekChatModel')
        update(progress, model=clean_summary(payload['model']))
        from .state import atomic_json
        atomic_json(job, payload)
        projection = None
        if policy['source'] == 'righaven_core':
            from .capability_policy import stage_skills
            projection = jobs / (name + '-skills')
            stage_skills(policy, settings['skills'], projection)
            verify_projection(role,projection)
            if runtime_environment is not None:
                import hashlib
                fingerprint = hashlib.sha256()
                for source in sorted(projection.rglob('*')):
                    if source.is_file():
                        fingerprint.update(str(source.relative_to(projection)).encode()+b'\0'+source.read_bytes()+b'\0')
                runtime_environment.update(skill_revision=fingerprint.hexdigest(), skills=settings['skills'])
                payload['environment'] = runtime_environment
                atomic_json(job, payload)
        installation = (STATE / 'installation-id').read_text().strip()
        restrictions = []
        if policy['blocked']:
            blocker = STATE / 'tool-disabled'
            if blocker.is_symlink():
                raise ValueError('Blocco strumenti non valido')
            blocker.write_text('#!/bin/sh\necho "Strumento non autorizzato per questo incarico" >&2\nexit 126\n')
            blocker.chmod(0o755)
            restrictions = worker_arguments(policy, host_path(blocker), projected_skills=projection is not None)
        if projection is not None:
            restrictions += ['--mount', mount(projection, '/mnt/skills/custom', True)]
        args = base_arguments(name, resources) + runtime_arguments(skills=projection is None) + provider_arguments(provider) + restrictions + ['--label', f'org.righaven.harness.installation={installation}',
            '--label', f'org.righaven.harness.workspace={workspace_key(workspace)}',
            *staging.mounts(mount, progress),
            '--mount', (mount(credentials.directory/'api.json' if credentials is not None else custom_connection_path(settings.get('connection_id')), '/credentials/api.json', True)
                        if engine == 'openai' else mount(credentials.directory if credentials is not None else credential_dir(engine), '/credentials', read_only=engine == 'deepseek')),
            '--mount', mount(job, '/job.json', True), *connections.mount_arguments(mount),
            runtime_image, 'python3', '/opt/righaven-worker/run_agent.py', '/job.json']
        from .egress_policy import mode as egress_mode
        if egress_mode() == 'allowlist':
            from .egress_policy import allowed_domains
            from .worker_egress import Grant, ensure as ensure_egress
            ensure_egress()
            egress = Grant(name, list(dict.fromkeys(allowed_domains(engine, (role or {}).get('network'), settings.get('base_url', '')) + connections.domains)))
            args = egress.arguments(args)
            update(progress, egress={'mode': 'allowlist', 'domains': egress.domains, 'refused': []})
        from .task_staging import forward_worker_events
        with forward_worker_events(workspace, progress), watch(lambda: request_stop(workspace, name), lambda: lifecycle(progress, cancel_error=True)):
            completed = subprocess.run(['docker', *args], capture_output=True, text=True,
                                       timeout=1560)
        lifecycle(progress, worker_exit_at=utcnow())
        response = completed.stdout
        if completed.returncode:
            status = read_status(progress)
            if status['phase'] not in ('failed', 'timed_out'):
                update(progress, 'failed')
            try:
                failure = json.loads(response)
            except (ValueError, TypeError):
                failure = {}
            if not isinstance(failure, dict):
                failure = {}
            error = ('Interruzione della fase richiesta dall’utente; i file salvati sono conservati.' if status.get('cancel_requested') else failure.get('error') or completed.stderr or 'Specialista non completato')
            try:
                container_state = json.loads(docker('inspect', '--format', '{{json .State}}', name))
                if isinstance(container_state, dict) and container_state.get('OOMKilled') is True:
                    error = 'Memoria esaurita confermata dallo stato del container. ' + error
                    previous_usage = read_status(progress).get('resources') or {}
                    update(progress, resources={**previous_usage, 'oom_kills': max(1, previous_usage.get('oom_kills', 0))})
            except (OSError, ValueError, TypeError, subprocess.SubprocessError):
                pass  # Unknown cause must not be invented from exit 137.
            recovered = recover_saved(args, progress, workspace, output_dir, error, policy=policy,role=role,staging=staging,early=read_status(progress).get('finish_requested',False))
            if recovered:
                remove(name)
                publish_staged(staging, recovered, progress)
                return completed_result({**recovered, 'environment': runtime_environment}, workspace, progress, runtime_image)
            attention = failure_info(error)
            available = []  # Failed staging is private, never advertised as a delivery.
            update(progress, 'failed', attention['message'], error_code=attention['code'],
                   action=attention['action'])
            return json.dumps({'ok': False, 'agent': agent_id, 'engine': engine, 'output_dir': output_dir,
                               'runtime_image': runtime_image,'tool_versions':(runtime_environment or {}).get('version_names',{}),
                               'error': clean_summary(error), 'attention': attention, 'available_files': available,
                               'partial': True, 'staging_status': 'quarantined', 'resume': 'File conservati nello staging privato per diagnosi; nessun risultato pubblicato. '
                               'Assegna una correzione mirata; le consegne precedenti restano inalterate.'}, ensure_ascii=False)
        try:
            result = json.loads(response)
        except (ValueError, TypeError):
            raise RuntimeError('Risposta JSON dello specialista non valida') from None
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise RuntimeError('Lo specialista non ha confermato il completamento')
        remove(name)  # No live writer may race host validation or publication.
        if read_status(progress).get('finish_requested'):result['user_requested_delivery']=True
        publish_staged(staging, result, progress)
        return completed_result({**result, 'environment': runtime_environment}, workspace, progress, runtime_image)
    except subprocess.TimeoutExpired:
        if 'args' in locals():
            recovered = recover_saved(args, progress, workspace, output_dir, 'Command worker timed out after 1500 seconds', policy=policy,role=role,staging=staging,early=read_status(progress).get('finish_requested',False))
            if recovered:
                remove(name)
                publish_staged(staging, recovered, progress)
                return completed_result({**recovered, 'environment': runtime_environment}, workspace, progress, runtime_image)
        update(progress, 'timed_out')
        return json.dumps({'ok': False, 'agent': agent_id, 'output_dir': output_dir,
                           'available_files': [], 'staging_status': 'quarantined',
                           'partial': True, 'error': 'Limite della singola fase raggiunto (25 minuti più chiusura).',
                           'resume': 'Il container viene rimosso; lo staging privato viene conservato per diagnosi. '
                           'Nessun file provvisorio viene pubblicato nel progetto.'}, ensure_ascii=False)
    except Exception:
        # Retain a more specific worker timeout or failed-delivery explanation.
        try:
            if read_status(progress)['phase'] not in ('failed', 'timed_out'):
                update(progress, 'failed')
        except (OSError, ValueError):
            pass
        raise
    finally:
        lifecycle(progress, cleanup_started_at=utcnow())
        try:
            remove(name)
        except Exception:
            from .resource_budget import BUDGET
            BUDGET.quarantine('Pulizia del worker non confermata')
            WORKERS.quarantine('Pulizia del worker non confermata')
            update(progress, 'failed', 'Pulizia del worker non confermata: la squadra richiede un controllo', cleanup_error=True)
            raise
        from .resource_budget import BUDGET
        BUDGET.release(name)
        lifecycle(progress, cleanup_finished_at=utcnow(), resources_reclaimed=True)
        try:
            from .environment_runtime import release_claim
            release_claim(name)
            if 'credentials' in locals() and credentials is not None:
                credentials.close()
            if 'connections' in locals():
                connections.close()
            if 'egress' in locals():
                from .worker_egress import summary
                try:
                    refused = summary(egress.close())
                    update(progress, egress={'mode': 'allowlist', 'domains': egress.domains, 'refused': refused})
                except (OSError, ValueError):
                    refused = []
                if refused:
                    from .audit_log import append
                    append(workspace, 'Rete', 'Connessioni in uscita bloccate', 'blocked',
                           ', '.join(f"{r['destination']} ×{r['attempts']}" for r in refused), correlation=name)
            if 'staging' in locals():
                staging.quarantine()
            release_prepared_environment(runtime_environment, ephemeral_environment)
            if 'job' in locals():
                job.unlink(missing_ok=True)
            if 'projection' in locals() and projection is not None:
                import shutil
                shutil.rmtree(projection, ignore_errors=True)
        finally:
            WORKERS.release()


def request_stop(workspace, job_id):
    """Stop only a worker bound by Docker labels to this installation and conversation."""
    from .progress import job_path, workspace_key, TERMINAL
    path = job_path(workspace, job_id)
    status = read_status(path)
    if status.get('workspace_key') != workspace_key(workspace) or status['phase'] in TERMINAL:
        raise ValueError('Questa fase non è più in esecuzione nella conversazione')
    if QUEUE.cancel(path):
        return {'requested': True, 'job_id': job_id, 'queued': True}
    if status.get('execution_state') == 'resources' or (status['phase'] == 'preparing_environment' and not status.get('environment_container')):
        update(path, cancel_requested=True)
        return {'requested': True, 'job_id': job_id, 'waiting_resources': True}
    target = status.get('environment_container') if status['phase']=='preparing_environment' else job_id
    target = target or job_id
    if target != job_id and not __import__('re').fullmatch(r'rh-env-[0-9a-f]{12}-[0-9a-f]{6}',target):
        raise ValueError('Preparatore non valido')
    info = json.loads(docker('inspect', '--format', '{{json .}}', target, timeout=10))
    labels = info.get('Config', {}).get('Labels') or {}
    if (labels.get('org.righaven.harness.installation') != (STATE / 'installation-id').read_text().strip()
            or labels.get('org.righaven.harness.workspace') != workspace_key(workspace)
            or not info.get('State', {}).get('Running')):
        raise ValueError('Il worker non è controllabile da questa conversazione o è già terminato')
    update(path, cancel_requested=True)
    try:
        docker('stop', '--time', '10', target, timeout=20)
    except (OSError, subprocess.SubprocessError):
        update(path, cancel_requested=False)
        raise
    return {'requested': True, 'job_id': job_id}


def request_finish(workspace,job_id):
    from .progress import job_path,TERMINAL
    path=job_path(workspace,job_id);status=read_status(path)
    if status.get('workspace_key')!=workspace_key(workspace):raise ValueError('Incarico estraneo al progetto')
    if status['phase'] in TERMINAL:return {'job_id':job_id,'already_finished':True}
    update(path,finish_requested=True)
    if status['phase']=='queued':QUEUE.cancel(path);return {'job_id':job_id,'queued':True}
    if status['phase'] in ('checking','finalizing','preparing_environment') or status.get('execution_state')=='resources':
        return {'job_id':job_id,'closing':True}
    installation=(STATE/'installation-id').read_text().strip()
    def signal_worker(signal):
        info=json.loads(docker('inspect','--format','{{json .}}',job_id,timeout=10))
        labels=info.get('Config',{}).get('Labels') or {}
        if labels.get('org.righaven.harness.installation')!=installation or labels.get('org.righaven.harness.workspace')!=workspace_key(workspace):
            raise ValueError('Container non controllabile da questo progetto')
        if info.get('State',{}).get('Running'):docker('kill','--signal',signal,job_id,timeout=15)
    def deadline():
        # Launching has a race between creating and starting the named container.
        # Poll the flag until it is running; verification/publication is never interrupted.
        until=time.monotonic()+30
        while time.monotonic()<until:
            current=read_status(path)
            if current.get('phase') in (*TERMINAL,'checking','finalizing'):return
            if current.get('execution_state')!='launching':
                try:signal_worker('USR1');break
                except (OSError,ValueError,subprocess.SubprocessError):pass
            time.sleep(.25)
        time.sleep(10)
        try:
            if read_status(path).get('phase') not in (*TERMINAL,'checking','finalizing'):signal_worker('TERM')
        except (OSError,ValueError,subprocess.SubprocessError):pass
    threading.Thread(target=deadline,daemon=True,name='delivery-close').start()
    return {'job_id':job_id,'closing':True}
