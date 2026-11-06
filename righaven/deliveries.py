"""Runtime-owned delivery identity and technical acceptance, separate from taste."""
import json
from pathlib import Path
import subprocess
import zipfile

try:
    from .source_packages import digest, verify_archive, sample, NATIVE, DEPENDENT_PROJECTS, inspect_blend, inspect_ebook, inspect_freecad, PRODUCTION_NATIVE, inspect_production, DESIGN_NATIVE, inspect_design
    from .acceptance import METHODS, evaluate, checkpoint_assessment, capabilities
    from .revision import actions, comparison, findings
    from .handoff import blocking_checks
    from .source_packages import inspect_office, OFFICE_PARTS
except ImportError:
    from source_packages import digest, verify_archive, sample, NATIVE, DEPENDENT_PROJECTS, inspect_blend, inspect_ebook, inspect_freecad, PRODUCTION_NATIVE, inspect_production, DESIGN_NATIVE, inspect_design
    from acceptance import METHODS, evaluate, checkpoint_assessment, capabilities
    from revision import actions, comparison, findings
    from handoff import blocking_checks
    from source_packages import inspect_office, OFFICE_PARTS


def read_review(handoff, output_dir, workspace, engine, acceptance=None):
    """Read a separate review of an existing product, never of a self-made export."""
    path = Path(output_dir) / 'quality-review.json'
    if path.is_symlink() or not path.is_file() or str(path) not in handoff['output_files'] or path.stat().st_size > 30000:
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Revisione: rapporto JSON non valido')
    target = Path(value.get('product_path', '')).resolve()
    if (not target.is_relative_to(Path(workspace).resolve()) or target.is_relative_to(Path(output_dir).resolve())
            or str(target) not in handoff['source_files'] or not target.is_file()):
        raise ValueError('La revisione deve riguardare un prodotto esistente in source_files, non un nuovo export')
    if value.get('product_sha256') and value['product_sha256'] != digest(target):
        raise ValueError('Revisione: il prodotto è cambiato rispetto all’hash osservato')
    criteria = value.get('criteria', [])
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 20:
        raise ValueError('Revisione: specificare criteri concreti del brief')
    reference_hashes = {}
    limits=value.get('observation_limits',[])
    if (not isinstance(limits,list) or len(limits)>7 or any(not isinstance(item,dict)
            or item.get('method') not in METHODS or any(not isinstance(item.get(k),str) or not item[k].strip()
            or len(item[k])>800 for k in ('reason','next_action')) for item in limits)):
        raise ValueError('Observation limits require method, reason and a concrete next_action.')
    unavailable={item['method'] for item in limits}
    for criterion in criteria:
        if (not isinstance(criterion, dict) or not criterion.get('criterion') or not criterion.get('evidence')
                or criterion.get('status') not in ('passed', 'failed', 'not_run')
                or criterion.get('method') not in METHODS):
            raise ValueError('Revisione: criterio, metodo, stato ed evidenza obbligatori')
        if criterion.get('blocked_by') is not None and criterion['blocked_by'] not in METHODS:
            raise ValueError('blocked_by must identify an observation method.')
        if criterion.get('status')!='failed' and (criterion['method'] in unavailable or criterion.get('blocked_by') in unavailable):
            criterion['status']='not_run'
        if criterion.get('method') == 'reference' and criterion.get('status') == 'passed':
            rule = next((r for r in (acceptance or {}).get('criteria', []) if r['id'] == criterion.get('requirement_id')), {})
            paths = rule.get('reference_paths', [])
            if not paths:
                criterion.update(status='not_run', evidence='Confronto con riferimento senza un riferimento disponibile e verificabile.')
            else:
                for filename in paths:
                    reference = Path(filename).resolve()
                    if not reference.is_relative_to(Path(workspace).resolve()) or not reference.is_file() or str(reference) not in handoff['source_files']:
                        criterion.update(status='not_run', evidence='Il riferimento necessario non è stato letto o non è disponibile.')
                    else:
                        reference_hashes[str(reference)] = digest(reference)
    visual = not acceptance and target.suffix.lower() in ('.mp4', '.mov', '.webm', '.gif', '.png', '.jpg', '.jpeg', '.pdf', '.svg', '.glb')
    audio = not acceptance and target.suffix.lower() in ('.wav', '.mp3', '.m4a', '.ogg')
    for needed, method in ((visual, 'visual'), (audio, 'listening')):
        if needed and not any(c['method'] == method for c in criteria):
            criteria.append({'criterion': 'Qualità del contenuto ' + method, 'method': method,
                             'status': 'not_run', 'evidence': 'Il rapporto contiene soltanto controlli di altre modalità.'})
    checkpoint = checkpoint_assessment(value.get('scope'), criteria, acceptance, engine)
    criteria, status = evaluate(criteria, acceptance, engine)
    observations = findings(value, criteria)
    corrections = actions(value, criteria)
    comparison_warning = ''
    if value.get('baseline_path') and not value.get('comparison'):
        # Keep independently validated criteria, never invent a before/after
        # claim when a first review supplies an unused or mistaken baseline.
        compared = None
        comparison_warning = 'Confronto non verificato: baseline indicata senza osservazioni prima/dopo. Conservati i criteri sul prodotto esaminato.'
        if status == 'passed':
            status = 'needs_review'
    else:
        compared = comparison(value, criteria, handoff, workspace, target, digest, engine)
    if compared:
        reference_hashes[compared['baseline_path']] = compared['baseline_sha256']
    return {'product_path': str(target), 'sha256': digest(target), 'criteria': criteria,
            'status': status, 'checkpoint': checkpoint, 'findings': observations,
            'unavailable_methods': sorted({c['method'] for c in criteria if c['status'] == 'not_run'
                                           and not capabilities(engine).get(c['method'], False)}|unavailable),
            'observation_limits':limits,
            'input_hashes': {str(Path(p).resolve()): digest(p) for p in handoff.get('source_files', [])
                             if Path(p).is_file() and Path(p).resolve().is_relative_to(Path(workspace).resolve())},
            'revision_actions': corrections, 'comparison': compared,
            'comparison_warning': comparison_warning, 'contract_hash': (acceptance or {}).get('hash'),
            'reference_hashes': reference_hashes,
            'report_path': str(path), 'report_sha256': digest(path), 'note': 'Valutazione dello specialista; non una garanzia oggettiva di qualità artistica.'}


def prepare_review_handoff(output_dir, workspace, engine, acceptance=None):
    """Wrap an existing, valid review report; never fabricate a quality verdict.

    Review jobs deliver an assessment, not a second copy of the product. A
    missing or invalid bookkeeping envelope must not discard their assessment.
    """
    root, boundary = Path(output_dir).resolve(), Path(workspace).resolve()
    manifest, report = root / 'handoff.json', root / 'quality-review.json'
    previous = {}
    original = None
    if manifest.is_symlink():
        raise ValueError('Revisione: involucro collegato fuori dal protocollo')
    if manifest.exists():
        try:
            try:
                from .handoff import validate_handoff
            except ImportError:
                from handoff import validate_handoff
            validate_handoff(root, boundary, require_delivery=True)
            return False
        except ValueError:
            if manifest.stat().st_size > 100000:
                raise ValueError('Revisione: involucro troppo grande')
            original = manifest.read_bytes()
            try:
                previous = json.loads(original)
            except ValueError:
                previous = {}
            if not isinstance(previous, dict):
                previous = {}
    if report.is_symlink() or not report.is_file() or report.stat().st_size > 30000:
        return False
    value = json.loads(report.read_text())
    if not isinstance(value, dict):
        raise ValueError('Revisione: rapporto JSON non valido')
    sources = value.get('source_files', previous.get('source_files', []))
    if not isinstance(sources, list) or len(sources) > 100:
        raise ValueError('Revisione: input non validi')
    sources = [s for s in [value.get('product_path'), value.get('baseline_path'), *sources] if s is not None]
    if any(not isinstance(s, str) or not Path(s).is_absolute() or not Path(s).resolve().is_relative_to(boundary)
           or not Path(s).is_file() for s in sources):
        raise ValueError('Revisione: input mancante o fuori dalla conversazione')
    sources = list(dict.fromkeys(sources))
    handoff = {'task':'Revisione del prodotto esistente', 'source_files':sources,
        'output_files':[str(report)], 'previews':[],
        'checks':[{'name':'Rapporto di revisione', 'status':'passed',
                   'evidence':'Rapporto JSON acquisito e validato dal runtime; questo controllo non approva il prodotto.'}],
        'warnings':['Involucro di consegna compilato dal runtime dal rapporto esistente; i giudizi restano quelli del revisore.'],
        'delivery':{'source_status':'not_applicable', 'source_note':'Consegna di un rapporto sul prodotto esistente, senza rigenerazione.',
            'files':[{'path':str(report), 'role':'report', 'format':'JSON', 'open_with':'Editor JSON',
                      'editability':'Rapporto testuale', 'reopen':{'status':'passed','evidence':'JSON letto e validato dal runtime.'},
                      'limitations':['I giudizi dipendono dalle evidenze del revisore e dalle capacità effettive del collegamento.']}]}}
    # Keep meaningful failed checks rather than making a broken envelope a way
    # to erase an unfavorable assessment. All original metadata stays on disk.
    for check in previous.get('checks', []) if isinstance(previous.get('checks'), list) else []:
        if (isinstance(check, dict) and check.get('status') in ('passed', 'failed', 'not_run')
                and all(isinstance(check.get(k), str) and check[k].strip() for k in ('name', 'evidence'))):
            handoff['checks'].append({k:check[k] for k in ('name','status','evidence','scope','superseded_by','policy_check') if k in check})
    # Validate the real product, criteria and baseline before writing anything.
    read_review(handoff, root, boundary, engine, acceptance)
    if original is not None:
        backup = root / 'work/review-handoff-original.json'
        if backup.is_symlink() or not backup.resolve().is_relative_to(root):
            raise ValueError('Revisione: percorso di recupero non valido')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists() and backup.read_bytes() != original:
            raise ValueError('Revisione: involucro originale già conservato con dati diversi')
        backup.write_bytes(original)
    manifest.write_text(json.dumps(handoff, ensure_ascii=False, indent=2))
    return True


def build_delivery(handoff, output_dir, *, purpose='work', native=True, agent='', tools=(), require_components=False, require_timing=False, workspace=None, verified_archives=None):
    root = Path(output_dir)
    delivery = handoff['delivery']
    issues, files, packages = [], [], []
    for item in delivery['files']:
        path = Path(item['path'])
        record = {**item, 'sha256': digest(path), 'size': path.stat().st_size}
        if path.suffix.lower() in OFFICE_PARTS and item['role'] in ('export','editable_source'):
            try:
                record['verification'] = inspect_office(path)
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                record['verification'] = {'status':'failed', 'method':'structural', 'error':str(error)[:1000]}
                issues.append(path.name + ': ' + str(error)[:1000])
        if path.suffix.lower() == '.blend' and item['role'] == 'editable_source':
            try:
                record['verification'] = inspect_blend(path, root, native=native)
                if record['verification']['status'] != 'passed':
                    issues.append(path.name + ': verifica Blender non eseguita')
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                record['verification'] = {'status': 'failed', 'error': str(error)[:1000]}
                issues.append(path.name + ': ' + str(error)[:1000])
        if path.suffix.lower() in ('.epub', '.azw3') and item['role'] in ('export', 'editable_source'):
            try:
                record['verification'] = inspect_ebook(path, root, native=native)
                if record['verification']['status'] != 'passed':
                    issues.append(path.name + ': controllo Calibre non eseguito')
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                record['verification'] = {'status': 'failed', 'error': str(error)[:1200]}
                issues.append(path.name + ': ' + str(error)[:1200])
        if path.suffix.lower() == '.fcstd' and item['role'] == 'editable_source':
            try:
                record['verification'] = inspect_freecad(path, root, native=native)
                if record['verification']['status'] != 'passed':
                    issues.append(path.name + ': verifica FreeCAD non eseguita')
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                record['verification'] = {'status': 'failed', 'error': str(error)[:1000]}
                issues.append(path.name + ': ' + str(error)[:1000])
        if path.suffix.lower() in DESIGN_NATIVE and item['role']=='editable_source':
            try:
                record['verification']=inspect_design(path,root,native=native)
                if record['verification']['status']!='passed':issues.append(path.name+': modello non verificato nativamente')
            except (OSError,ValueError,subprocess.SubprocessError) as error:
                record['verification']={'status':'failed','error':str(error)[:1000]};issues.append(path.name+': '+str(error)[:1000])
        if path.suffix.lower() in PRODUCTION_NATIVE and item['role'] == 'editable_source':
            try:
                record['verification'] = inspect_production(path, root, native=native)
                if record['verification']['status'] != 'passed':
                    issues.append(path.name + ': riapertura nativa non eseguita')
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                record['verification'] = {'status':'failed','error':str(error)[:1000]}
                issues.append(path.name + ': ' + str(error)[:1000])
        if item['role'] == 'source_archive':
            try:
                if path.suffix.lower() != '.zip':
                    raise ValueError('Archivio sorgenti: usare ZIP per il collaudo di trasferimento')
                cached = (verified_archives or {}).get(record['sha256'])
                if cached and cached.get('status') == 'passed' and cached.get('sha256') == record['sha256']:
                    record['verification'] = {**cached, 'reused': True}
                else:
                    record['verification'] = verify_archive(path, native=native)
                if record['verification']['status'] != 'passed':
                    issues.append(path.name + ': controlli nativi del pacchetto non eseguiti')
                packages.append(record)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                record['verification'] = {'status': 'failed', 'error': str(error)[:1000]}
                issues.append(path.name + ': ' + str(error)[:1000])
        structurally_opened = (path.suffix.lower() in OFFICE_PARTS and
            record.get('verification',{}).get('status') == 'passed' and item['reopen']['status'] == 'not_run')
        if item['role'] in ('editable_source', 'source_archive') and item['reopen']['status'] != 'passed' and not structurally_opened:
            issues.append(path.name + ': riapertura non verificata')
        files.append(record)
    if delivery['source_status'] == 'unavailable':
        issues.append('Sorgenti modificabili mancanti: ' + delivery['source_note'])
    finalization = []
    if any(Path(f['path']).suffix.lower() in DEPENDENT_PROJECTS and f['role'] == 'editable_source' for f in files) and not packages:
        note = 'Progetto nativo con risorse collegate: serve il pacchetto sorgenti ZIP completo e verificato'
        (finalization if purpose == 'preview' else issues).append(note)
    for item in files:
        if Path(item['path']).suffix.lower() in DEPENDENT_PROJECTS and item['role'] == 'editable_source':
            if purpose == 'preview' and not packages:
                item['limitations'] = [*item.get('limitations', []), 'Sorgente della prova; il pacchetto portabile finale resta da preparare con le risorse collegate.']
            else:
                item['open_with'] = 'Usa il pacchetto sorgenti ZIP della stessa consegna e le sue istruzioni; questo progetto isolato può perdere i media.'
                item['limitations'] = [*item.get('limitations', []), 'Il progetto scaricato da solo non include le risorse collegate.']
    if purpose == 'delivery':
        for suffix in {Path(f['path']).suffix.lower() for f in files if f['role']=='editable_source'} & (DEPENDENT_PROJECTS & PRODUCTION_NATIVE.keys()):
            expected=PRODUCTION_NATIVE[suffix][0]+'_reopen'
            if not any(c.get('check')==expected and c.get('status')=='passed'
                       for package in packages for c in package['verification'].get('checks',[])):
                issues.append('Il pacchetto sorgenti ZIP deve contenere il progetto '+suffix+' con le risorse e una riapertura nativa verificata')
    renders = [c for p in packages for c in p['verification']['checks'] if c.get('check') == 'filmcraft_render']
    # A role's toolbox is availability, not proof that every engine authored
    # this delivery. New handoffs identify the producers per component; legacy
    # handoffs retain the strict toolbox fallback. A direct native specialist
    # still requires its own native project regardless of component labels.
    component_tools = {c['tool'] for c in delivery.get('components', []) if c.get('tool')}
    active_tools = {agent, *(component_tools or tools)}
    if purpose == 'delivery' and 'filmcraft' in active_tools and delivery['source_status'] == 'included' and not renders:
        issues.append('Consegna FilmCraft senza progetto .fcproj collaudato nel pacchetto: README o soli video non sono il sorgente di montaggio')
    if purpose == 'delivery' and 'blender' in active_tools and not any(
            (f['role'] == 'editable_source' and Path(f['path']).suffix.lower() == '.blend'
             and f.get('verification', {}).get('status') == 'passed') or
            (f['role'] == 'source_archive' and any(c.get('check') == 'blender_reopen' and c.get('status') == 'passed'
                for c in f.get('verification', {}).get('checks', []))) for f in files):
        issues.append('Consegna Blender senza .blend modificabile riaperto e verificato: GLB, script o video da soli non sono il progetto nativo')
    if purpose == 'delivery' and 'freecad' in active_tools and not any(
            (f['role'] == 'editable_source' and Path(f['path']).suffix.lower() == '.fcstd'
             and f.get('verification', {}).get('status') == 'passed') or
            (f['role'] == 'source_archive' and any(c.get('check') == 'freecad_reopen' and c.get('status') == 'passed'
                for c in f.get('verification', {}).get('checks', []))) for f in files):
        issues.append('Consegna FreeCAD senza .FCStd modificabile riaperto e verificato: STEP, mesh o script da soli non sono il progetto parametrico')
    if purpose == 'delivery' and renders:
        for item in files:
            if item['role'] != 'export' or Path(item['path']).suffix.lower() not in ('.mp4', '.mov', '.webm', '.mkv'):
                continue
            try:
                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', item['path']],
                                       capture_output=True, text=True, check=True, timeout=30)
                info = json.loads(probe.stdout)
                video = next(s for s in info['streams'] if s['codec_type'] == 'video')
                matches = []
                for rendered in renders:
                    if rendered.get('sample_format') != 'rgb24-area-v1':
                        continue
                    if (abs(float(info['format']['duration']) - rendered['duration']) > .15
                            or video['width'] != rendered['width'] or video['height'] != rendered['height']):
                        continue
                    errors = [sum(abs(a-b) for a, b in zip(sample(item['path'], s['seconds']), s['luma'])) / len(s['luma'])
                              for s in rendered['samples']]
                    if max(errors) <= 12:
                        matches.append({'source': rendered['file'], 'mean_luma_errors': errors})
                item['source_match'] = matches
                if not matches:
                    issues.append(Path(item['path']).name + ': il render dei sorgenti non corrisponde al video consegnato (durata, dimensioni o tre fotogrammi)')
            except (OSError, ValueError, StopIteration, subprocess.SubprocessError) as error:
                issues.append('Confronto sorgente/video non completato: ' + str(error)[:300])
    try:
        from .component_sources import inspect_components
        from .timing import check_timing
    except ImportError:
        from component_sources import inspect_components
        from timing import check_timing
    coverage=inspect_components(handoff, files, required=require_components and delivery['source_status'] != 'not_applicable', workspace=workspace)
    timing=check_timing(handoff, required=require_timing)
    issues.extend(coverage['issues'])
    if timing['status'] == 'failed':
        issues.extend(timing['issues'])
    issues.extend(c['name'] + ': ' + c['evidence'][:300] for c in blocking_checks(handoff['checks']))
    value = {'id': root.name, 'title': handoff['task'][:200], 'purpose': purpose,
             'technical_status': 'passed' if not issues else 'needs_revision',
             'issues': issues[:20], 'finalization_pending': finalization, 'files': files, 'source_status': delivery['source_status'],
             'environment_checks': [c for c in handoff['checks'] if c.get('scope') == 'environment'],
             'historical_checks': [c for c in handoff['checks'] if c.get('scope') == 'historical'],
             'source_coverage':coverage, 'timing':timing,
             'source_package_status': ('not_applicable' if delivery['source_status']=='not_applicable' else
                 'verified' if packages and all(p.get('verification',{}).get('status')=='passed' for p in packages) and not issues and not finalization
                 else 'incomplete' if any(f['role']=='source_archive' for f in files) or finalization else 'not_packaged'),
             'source_note': delivery['source_note'][:1000],
             'quality_status': 'not_reviewed',
             'reused_archive_checks': sum(bool(p.get('verification',{}).get('reused')) for p in packages),
             'note': 'I controlli tecnici non certificano qualità visiva, musicale o aderenza creativa al brief.'}
    # Owned by the runtime; never trust a model-authored file with this name.
    path = root / 'delivery-manifest.json'
    if path.is_symlink():
        raise ValueError('Manifesto di consegna non valido')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    return value
