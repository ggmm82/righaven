"""Runs inside a disposable container. All tools act on this thread's files."""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

try:
    from .handoff import validate_handoff, blocking_checks
    from .progress import Reporter, utcnow
    from .cli_runner import run_cli
    from .work_results import validate_media
    from .deliveries import build_delivery, read_review, prepare_review_handoff
    from .acceptance import capabilities
except ImportError:  # Direct invocation inside the worker image.
    from handoff import validate_handoff, blocking_checks
    from progress import Reporter, utcnow
    from cli_runner import run_cli
    from work_results import validate_media
    from deliveries import build_delivery, read_review, prepare_review_handoff
    from acceptance import capabilities

ALLOWED_AUTH = {
    'codex': ('auth.json',),
    'deepseek': ('api.json',),
}


def learning_status(output_dir):
    path = output_dir / 'work/tool-lessons.json'
    if not path.is_file() or path.is_symlink():
        return 'not_recorded'
    if not path.resolve().is_relative_to(output_dir.resolve()) or path.stat().st_size > 24000:
        return 'invalid'
    try:
        value = json.loads(path.read_text())
        candidates = value if isinstance(value,list) else value['lessons']
        if not isinstance(candidates,list) or len(candidates)>3:
            return 'invalid'
        return 'recorded' if candidates else 'no_findings'
    except (OSError,ValueError,KeyError,TypeError):
        return 'invalid'


def copy_credentials(source, destination, engine):
    if engine == 'gemini':
        try:
            from .antigravity_cli import copy_auth
        except ImportError:
            from antigravity_cli import copy_auth
        return copy_auth(source, destination)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for filename in ALLOWED_AUTH[engine]:
        path = source / filename
        if path.is_symlink():
            raise ValueError('Link nelle credenziali non consentiti')
        if path.is_file():
            target = destination / filename
            if target.is_symlink():
                raise ValueError('Destinazione credenziali non valida')
            shutil.copyfile(path, target)
            target.chmod(0o600)


def command(engine, model, prompt, output):
    if engine == 'gemini':
        args = ['agy', '--dangerously-skip-permissions', '--input-format', 'stream-json', '--output-format', 'stream-json',
                '--add-dir', '/mnt/user-data', '--print-timeout', '25m',
                '--json-schema', json.dumps({'type': 'object', 'properties': {
                    'summary': {'type': 'string'}}, 'required': ['summary']})]
        if model and model != 'auto':
            args += ['--model', model]
        return args
    raise ValueError('Motore non valido')


def worker_error(engine, result):
    """Prefer structured CLI failures; never return a quoted system prompt."""
    if engine == 'codex':
        errors = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') == 'turn.failed':
                errors.append(str(event.get('error', {}).get('message', 'Turno Codex fallito')))
            elif event.get('type') == 'error':
                errors.append(str(event.get('message', 'Errore Codex')))
        if errors:
            return errors[-1][:1200]
    lines = (result.stderr or '').splitlines()
    important = [line for line in lines if any(word in line.lower() for word in ('error:', 'error ', 'failed', 'permission denied', 'unauthorized', 'unsupported'))]
    return ('\n'.join(important[-4:]) or '\n'.join(lines[:4]) or 'Worker terminato senza dettagli diagnostici')[:1200]


def handoff_error(output_dir, error):
    """Keep a failed delivery failed, but expose the recorded operational cause."""
    details = []
    try:
        path = output_dir / 'handoff.json'
        if not path.resolve().is_relative_to(output_dir.resolve()):
            return str(error)[:1800]
        manifest = json.loads(path.read_text())
        for check in blocking_checks([c for c in manifest.get('checks', []) if isinstance(c,dict)]):
            if isinstance(check, dict) and check.get('status') == 'failed':
                evidence = check.get('evidence')
                if isinstance(evidence, str):
                    details.append(evidence[:500])
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return (str(error) + ('; ' + '; '.join(details[:3]) if details else ''))[:1800]


def verify_project_context(job, workspace=Path('/mnt/user-data'),skill_root=Path('/mnt/skills/custom')):
    import hashlib
    def read(document):
        path = workspace / Path(document['path']).relative_to('/mnt/user-data')
        if not path.resolve().is_relative_to(workspace.resolve()) or path.is_symlink():
            raise ValueError('Contesto fuori dal progetto')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != document['sha256']:
                raise ValueError('Contesto modificato rispetto alla richiesta corrente')
        return path
    acceptance = job.get('acceptance') or {}
    if (job.get('role') or {}).get('skill_bindings') or (job.get('role') or {}).get('package_bindings') or (job.get('environment') or {}).get('skill_revision'):
        try:from .skill_composition import verify_projection,package_revision
        except ImportError:from skill_composition import verify_projection,package_revision
        verify_projection(job.get('role'),skill_root)
        expected=(job.get('environment') or {}).get('skill_revision')
        if expected and package_revision(skill_root,require_skill=False)!=expected:raise ValueError('Proiezione skill diversa dal mandato di esecuzione')
    if acceptance.get('request_manifest'):
        manifest = read(acceptance['request_manifest'])
        for document in json.loads(manifest.read_text()):
            read(document)
    experience = (job.get('role') or {}).get('experience')
    if experience:
        read(experience)
    memory = (job.get('role') or {}).get('memory')
    if memory:
        memory_path = read(memory)
        method = json.loads(memory_path.read_text()).get('method_selection')
        if isinstance(method, dict) and 'path' in method and 'sha256' in method:
            read(method)


class WorkerFinishRequested(Exception):
    pass


def handle_finish(signum,frame):
    raise WorkerFinishRequested('Consegna anticipata richiesta dall’utente')


class WorkerCancelled(Exception):
    pass


def handle_stop(signum, frame):
    # Unwind through run_cli's process cleanup and the credential refresh finally.
    raise WorkerCancelled('Interruzione della fase richiesta dall’utente; i file salvati sono conservati.')


def finalize_saved(job, output_dir, workspace=Path('/mnt/user-data'), *, early=False):
    """Verify existing artifacts without credentials, a model call or regeneration."""
    output_dir, workspace = Path(output_dir).resolve(), Path(workspace).resolve()
    expected = workspace / 'outputs' / job['agent'] / job['run_id']
    if output_dir != expected or not output_dir.is_relative_to(workspace) or not output_dir.is_dir():
        raise ValueError('Cartella di recupero non valida')
    if early:
        try:
            return finalize_saved(job,output_dir,workspace)
        except (ValueError,OSError):
            try:from .early_delivery import draft_handoff
            except ImportError:from early_delivery import draft_handoff
            draft_handoff(output_dir)
            result=finalize_saved({**job,'purpose':'preview','requirements':{}},output_dir,workspace)
            record=result['delivery_record'];record.update(technical_status='needs_revision',early_delivery=True,quality_status='not_reviewed')
            record.setdefault('issues',[]).insert(0,'Consegna anticipata: file disponibili, requisiti completi non verificati')
            (output_dir/'delivery-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
            return {**result,'early_delivery':True}
    engine = job['engine']
    learning_review = learning_status(output_dir)
    try:
        if job.get('purpose') == 'review':
            prepare_review_handoff(output_dir, workspace, engine, job.get('acceptance'))
        handoff = validate_handoff(output_dir, workspace, require_delivery=True)
    except ValueError as exc:
        raise ValueError(handoff_error(output_dir, exc)) from exc
    if learning_review in ('not_recorded','invalid'):
        handoff['warnings'].append('Valutazione delle lezioni non registrata: le prove restano disponibili, nessun apprendimento automatico dichiarato.')
    verified_products = []
    if job.get('requirements') and job.get('purpose') != 'review':
        candidates = [f for f in handoff['output_files'] if Path(f).suffix.lower() in
                      ('.mp4', '.mov', '.webm', '.mkv', '.wav', '.mp3', '.m4a')]
        if not candidates:
            raise ValueError('Manca il prodotto media finale da verificare')
        checked = False
        for candidate in candidates:
            checks = validate_media(candidate, job['requirements'])
            if checks and all(c['status'] == 'passed' for c in checks):
                checked = True
                verified_products.append(candidate)
                handoff['checks'].extend(checks)
                break
        if not checked:
            raise ValueError('Il prodotto finale non soddisfa i requisiti audio/video reali: '
                             'non consegnare come definitivo un render muto o un file audio silenzioso')
    delivery_record = build_delivery(handoff, output_dir, purpose=job.get('purpose', 'work'), agent=job['agent'],
                                     tools=(job.get('role') or {}).get('tools', []),
                                     require_components=job.get('purpose')=='delivery',
                                     require_timing=job.get('purpose')=='delivery' and all((job.get('requirements') or {}).get(k) for k in ('audio','video')),
                                     workspace=workspace, verified_archives=job.get('verified_archives'))
    delivery_record.update(requirements=job.get('requirements') or {}, verified_products=verified_products)
    if (output_dir / 'delivery-manifest.json').is_symlink():
        raise ValueError('Manifest di consegna non valido')
    (output_dir / 'delivery-manifest.json').write_text(json.dumps(delivery_record, ensure_ascii=False, indent=2))
    quality_review = read_review(handoff, output_dir, workspace, engine, job.get('acceptance')) if job.get('purpose') == 'review' else None
    return {'ok': True, 'agent': job['agent'], 'engine': engine,
            'output_dir': str(output_dir), 'handoff': handoff,
            'product_verified': bool(verified_products), 'verified_products': verified_products,
            'delivery_record': delivery_record, 'quality_review': quality_review,
            'learning_review': learning_review}


def main():
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGUSR1, handle_finish)
    recovering = sys.argv[1] in ('--finalize','--finalize-early')
    job = json.loads(Path(sys.argv[2] if recovering else sys.argv[1]).read_text())
    if recovering:
        verify_project_context(job)
        output = Path('/mnt/user-data/outputs') / job['agent'] / job['run_id']
        reporter = Reporter(output, {**job, 'model': job.get('model', '')}).start(300, preserve_started=True)
        try:
            reporter.emit('checking', 'Verifico i file salvati senza richiamare il modello', execution_state='tool')
            result = finalize_saved(job, output, Path('/mnt/user-data'),early=sys.argv[1]=='--finalize-early')
            reporter.emit('completed')
            print(json.dumps(result, ensure_ascii=False))
            return 0
        except Exception:
            reporter.emit('failed', 'Verifica dei file salvati non superata')
            raise
        finally:
            reporter.close()
    engine = job['engine']
    auth = Path('/root') / ('.' + engine)
    if engine not in ('deepseek', 'openai'):
        copy_credentials(Path('/credentials'), auth, engine)
    if engine == 'gemini':
        try:
            from .antigravity_cli import prepare_home, cli_env, result_envelope
        except ImportError:
            from antigravity_cli import prepare_home, cli_env, result_envelope
        prepare_home()
    output_dir = Path('/mnt/user-data/outputs') / job['agent'] / job['run_id']
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink() or any(output_dir.iterdir()):
        raise ValueError('Lo staging iniziale deve essere una cartella vuota e reale')
    (output_dir / 'work').mkdir()
    (output_dir / 'previews').mkdir()
    selected = []
    verify_project_context(job)
    skills_root = Path('/root/.agents/skills') if engine == 'codex' else auth / 'antigravity-cli/skills'
    for name in job['skills']:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name) or name in ('.', '..'):
            raise ValueError('Nome skill non valido')
        source = Path('/mnt/skills/custom') / name
        selected.append((source / 'SKILL.md').read_text())
        selected.append('Riferimenti della skill disponibili su disco: ' + str(source / 'references') +
                        '. Leggi solo le sezioni pertinenti alla fase corrente.')
        # Native skill discovery for either CLI, scoped to this disposable run.
        if engine not in ('deepseek', 'openai'):
            target = skills_root / name
            shutil.copytree(source, target, dirs_exist_ok=True)
    if job.get('compiled_skill'):
        import hashlib
        role = job['role']
        if hashlib.sha256(job['compiled_skill'].encode()).hexdigest() != role['skill']['sha256']:
            raise ValueError('Skill di progetto modificata rispetto alla versione assegnata')
        selected.append(job['compiled_skill'])
        if engine not in ('deepseek', 'openai'):
            target = skills_root / ('rh-project-' + role['id'])
            target.mkdir(parents=True, exist_ok=True)
            (target / 'SKILL.md').write_text(job['compiled_skill'])
    try:
        from .worker_context import build_prompt
    except ImportError:
        from worker_context import build_prompt
    prompt = build_prompt(job, selected, output_dir)
    prompt += '\nMetodi di osservazione disponibili: ' + json.dumps(capabilities(engine)) + '. Disponibile non significa eseguito; registra not_run se non osservato.'
    prompt += ('\nScelte esplicite dell’utente dal pannello (prevalgono su metodi preferiti e ipotesi): ' +
               json.dumps(job.get('user_direction'), ensure_ascii=False) +
               '\nUn’immagine raster inserita in un SVG non è un disegno vettoriale modificabile. '
               'Se la tecnica richiesta non è disponibile, riferisci il limite senza sostituirla in silenzio.')
    native_images = engine == 'codex' and (job.get('user_direction') or {}).get('visual_approach') != 'vector'
    if native_images:
        prompt += ('\nCapacità nativa configurata: image_gen.imagegen di Codex. Disponibilità effettiva soggetta a login, modello e quota. '
                   'Usala solo se coerente con la scelta dell’utente: non è obbligatoria. '
                   'Per gli asset generati consulta generated_images e work/imagegen-*.json: il runtime copia il PNG e registra prompt riveduto, hash e dimensioni reali. '
                   'Conserva inoltre in work i prompt originari e i riferimenti agli input effettivamente usati, senza credenziali. '
                   'Il PNG non contiene livelli separati: se servono testi e impaginazione modificabili, crea un progetto con quelle componenti separate e dichiara i limiti della parte raster.')
    if engine == 'gemini':
        prompt += ('\nChiusura obbligatoria Antigravity: quando file e handoff.json sono pronti, '
                   'chiama il tool nativo finish e consegna un oggetto con summary contenente '
                   'percorsi, verifiche e limiti. Non limitarti a ripetere un messaggio testuale: '
                   'finish conclude il processo. Non ricreare i file già verificati.')
    final = Path('/tmp/last-message.txt')
    import time
    os.environ['RIGHAVEN_JOB_DEADLINE'] = str(time.time() + job['timeout'])
    reporter = Reporter(output_dir, job).start(job['timeout'], preserve_started=True)
    reporter.emit('preparing', worker_started_at=utcnow())
    try:
        if engine in ('deepseek', 'openai'):
            if engine == 'openai':
                try:
                    from .openai_compatible import run
                except ImportError:
                    from openai_compatible import run
            else:
                try:
                    from .deepseek import run
                except ImportError:
                    from deepseek import run
            os.environ['RIGHAVEN_OUTPUT_DIR'] = str(output_dir)
            message = run(job['model'], prompt, output_dir, job['timeout'], progress=reporter)
        elif engine == 'codex':
            try:
                from .codex_native import run
            except ImportError:
                from codex_native import run
            reporter.model_wait_seconds = (job.get('resources') or {}).get('model_wait_seconds', 0)
            def preflight():
                if job.get('purpose') == 'review':
                    prepare_review_handoff(output_dir, Path('/mnt/user-data'), engine, job.get('acceptance'))
                validate_handoff(output_dir, Path('/mnt/user-data'), require_delivery=True)
            message = run(job['model'], prompt, output_dir, job['timeout'], reporter, image_generation=native_images, preflight=preflight)
        else:
            reporter.emit('waiting_model')
            result = run_cli(command(engine, job['model'], prompt, final), cwd=output_dir,
                                input=(json.dumps({'event': 'user', 'message': {'content': prompt}}) + '\n') if engine == 'gemini' else prompt,
                                env={**(cli_env() if engine == 'gemini' else os.environ), 'RIGHAVEN_OUTPUT_DIR': str(output_dir)},
                                timeout=job['timeout'], on_event=lambda event: reporter.cli_event(engine, event),
                                model_wait_seconds=(job.get('resources') or {}).get('model_wait_seconds', 0),
                                waiting_model=lambda: reporter.execution_state == 'model')
            if result.returncode:
                reporter.emit('failed')
                print(json.dumps({'ok': False, 'engine': engine, 'agent': job['agent'],
                              'exit_code': result.returncode,
                              'error': worker_error(engine, result)}))
                return result.returncode
            parsed = result_envelope(result.stdout)
            if parsed.get('status') != 'SUCCESS' or parsed.get('error'):
                try:
                    from .antigravity_cli import result_error
                except ImportError:
                    from antigravity_cli import result_error
                raise RuntimeError(result_error(parsed))
            message = parsed.get('structured_output', {}).get('summary')
            if not isinstance(message, str) or not message.strip():
                raise RuntimeError('Antigravity: manca la chiusura strutturata dello specialista')
        reporter.emit('checking')
        result = finalize_saved(job, output_dir, Path('/mnt/user-data'))
        reporter.emit('completed')
        print(json.dumps({**result, 'response': message}, ensure_ascii=False))
        return 0
    except WorkerFinishRequested:
        reporter.emit('finalizing','Consegna richiesta: il Gateway verificherà i file salvati')
        print(json.dumps({'ok':False,'finish_requested':True,'error':'Consegna anticipata richiesta'}))
        return 75
    except (TimeoutError, subprocess.TimeoutExpired):
        reporter.emit('timed_out')
        raise
    except Exception:
        reporter.emit('failed')
        raise
    finally:
        reporter.close()
        # One worker at a time. Preserve refreshed tokens for the next run.
        if engine not in ('deepseek', 'openai'):
            copy_credentials(auth, Path('/credentials'), engine)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)[-2000:]}))
        sys.exit(1)
