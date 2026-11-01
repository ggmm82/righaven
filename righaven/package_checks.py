"""Verify an exported data package in the application's internal runtime, without production access."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
import uuid

from . import state
from .progress import create_job, update, heartbeat, read_status, utcnow
from .project_store import workspace_path
from .resource_budget import BUDGET
from .cancellation import requested
from .source_packages import digest


class CheckCancelled(RuntimeError):
    pass


def templates():
    # Trusted release sources; never import code from the submitted project.
    source = Path(os.getenv('RIGHAVEN_WORKER_SOURCE', Path(__file__).resolve().parents[1])) / 'scripts'
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    import pipeline_scaffold
    return pipeline_scaffold, source


def validate(root):
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Select the exported package directory')
    paths = list(root.rglob('*'))
    if len(paths) > 4000 or any(p.is_symlink() for p in paths) or sum(p.stat().st_size for p in paths if p.is_file()) > 50*1024**2:
        raise ValueError('Package must contain at most 4000 files and 50 MiB, without symlinks')
    if any(p.name == '.env' or p.name.endswith(('.pem', '.key')) for p in paths):
        raise ValueError('Remove private credential files from the exported package')
    spec = json.loads((root / 'package-spec.json').read_text())
    template, sources = templates()
    if spec.get('target') not in template.DESTINATIONS or spec.get('source_dialect') not in template.SOURCE_DRIVERS:
        raise ValueError('Unsupported package target or source dialect')
    import re
    if not re.fullmatch(r'[a-z0-9_]{1,100}', str(spec.get('name', ''))):
        raise ValueError('Invalid package name')
    expected = {'Dockerfile': template.dockerfile(spec['target'], spec['source_dialect']),
                'ops/entrypoint.sh': template.ENTRYPOINT_SH,
                'ops/orchestrate.py': (sources/'pipeline_runtime.py').read_text(),
                'ingestion/pipeline.py': template.PIPELINE.replace('{name}',spec['name'])}
    locks = sources.parent/'config/toolkit/pipeline'
    for directory, name in [('ingestion','ingest'),('transform','transform')]:
        expected[directory+'/requirements.lock']=(locks/(name+'.lock')).read_text()
    if any(not (root/name).is_file() or (root/name).read_text()!=text for name,text in expected.items()):
        raise ValueError('Regenerate the managed package before testing: runtime, Dockerfile or dependency locks differ from this release')
    return {p.relative_to(root).as_posix():digest(p) for p in paths if p.is_file()}


def check(workspace, package_path):
    from .docker_runtime import docker, internal_daemon, base_arguments, remove
    package=workspace_path(workspace,package_path)
    outputs=Path(workspace).resolve()/'outputs'
    if not package or not package.resolve().is_relative_to(outputs):
        raise ValueError('Select a package saved in this project outputs directory')
    hashes=validate(package)
    if not internal_daemon():raise ValueError('Package verification requires the application-owned internal runtime')
    identifier=uuid.uuid4().hex[:12];job_id='rh-job-'+identifier
    progress=create_job(workspace,job_id,'workspace','verification','exported-package')
    output=outputs/'workspace'/job_id;output.mkdir(parents=True)
    image='righaven-package-check:'+identifier;worker='rh-package-'+identifier
    builder='rh-package-build-'+identifier;builder_container='buildx_buildkit_'+builder+'0';volume=worker+'-data'
    report={'status':'failed','package':package_path,'files':hashes,'checks':[], 'at':utcnow(),
            'scope':'Local synthetic execution only; no production connectivity or source-engine parity claim'}
    created_builder=False;lease=None
    class Cancel:
        def is_set(self):
            return requested() or read_status(progress).get('cancel_requested',False) or read_status(progress).get('finish_requested',False)
    cancel=Cancel()
    def command(*args, timeout=900):
        if cancel.is_set():raise CheckCancelled('Package verification cancelled')
        with (output/'commands.log').open('a') as log:
            log.write('$ docker '+shlex.join(args)+'\n');log.flush()
            process=subprocess.Popen(['docker',*args],stdout=log,stderr=log,text=True)
            deadline=time.monotonic()+timeout
            try:
                while process.poll() is None:
                    if cancel.is_set():raise CheckCancelled('Package verification cancelled')
                    if time.monotonic()>deadline:raise TimeoutError('Package verification command timed out')
                    time.sleep(.25)
                if process.returncode:raise RuntimeError('Package command failed; inspect the saved command log')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
    reclaimed=True
    root=state.STATE/'package-checks';root.mkdir(parents=True,exist_ok=True)
    try:
        with heartbeat(progress),tempfile.TemporaryDirectory(dir=root) as directory:
            context=Path(directory)/'package';shutil.copytree(package,context)
            if validate(context)!=hashes:raise ValueError('Package changed while preparing its verification')
            update(progress,'queued','Waiting for package verification resources',role_title='Package verification',started_at=utcnow())
            limits=BUDGET.acquire(builder_container,'build',cancel=cancel,timeout=600);lease=builder_container
            BUDGET.observe_progress(builder_container,progress)
            update(progress,'preparing','Building the exported package without production credentials',limits=limits)
            command('buildx','create','--name',builder,'--driver','docker-container','--driver-opt',
                    'memory='+str(limits['memory_mib'])+'m,memory-swap='+str(limits['memory_mib'])+'m,cpu-period=100000,cpu-quota='+str(int(limits['cpus']*100000)),timeout=60)
            created_builder=True
            command('buildx','build','--builder',builder,'--load','--tag',image,str(context))
            command('buildx','rm','--force',builder,timeout=60);created_builder=False
            BUDGET.release(lease);lease=None
            command('volume','create',volume,timeout=30)
            for cycle in (1,2):
                limits=BUDGET.acquire(worker,'worker',cancel=cancel,timeout=600);lease=worker
                BUDGET.observe_progress(worker,progress)
                update(progress,'checking','Testing exported package: cycle '+str(cycle)+' and saved state',limits=limits)
                args=base_arguments(worker,limits);args[args.index('--network=bridge')]='--network=none'
                command(*args,'-d','--read-only','--mount','type=volume,src='+volume+',dst=/data',
                        '-e','PIPELINE_ENV=test','-e','SQLMESH_GATEWAY=local','-e','STUB_ROWS=3','-e','STUB_ROWS_LIMIT=3',
                        '-e','RIGHAVEN_SOURCE_DUCKDB=/data/source-stub.duckdb','-e','RIGHAVEN_WAREHOUSE_DUCKDB=/data/warehouse.duckdb',image,timeout=60)
                deadline=time.monotonic()+300
                while time.monotonic()<deadline:
                    if cancel.is_set():raise CheckCancelled('Package verification cancelled')
                    try:cycle_state=json.loads(docker('exec',worker,'cat','/data/last-cycle.json',timeout=10))
                    except (ValueError,subprocess.SubprocessError):cycle_state={}
                    if cycle_state.get('status')=='failed':raise RuntimeError('Exported pipeline failed; inspect the saved container log')
                    if cycle_state.get('status')=='passed':break
                    time.sleep(1)
                else:raise TimeoutError('Exported pipeline did not complete its test cycle')
                if cycle==2:
                    command('exec',worker,'/opt/ingest/bin/python','/app/ops/orchestrate.py','cycle',timeout=300)
                    cycle_state=json.loads(docker('exec',worker,'cat','/data/last-cycle.json',timeout=10))
                command('exec',worker,'/opt/ingest/bin/python','/app/ops/orchestrate.py','health',timeout=20)
                (output/'reports').mkdir(exist_ok=True)
                command('cp',worker+':/data/reports/.',str(output/'reports'),timeout=30)
                report['checks'].append({'name':'cycle_'+str(cycle),'status':'passed','evidence':cycle_state})
                remove(worker);lease=None
            if validate(package)!=hashes:raise ValueError('Package changed after verification; test the new version')
            report['status']='passed'
    except (OSError,ValueError,RuntimeError,TimeoutError,subprocess.SubprocessError) as error:
        report['error']=str(error)[:2000]
    finally:
        # Remove both execution and build containers before returning admission capacity.
        try:
            try:
                logs=docker('logs',worker,timeout=10)
                (output/'container.log').write_text(logs[-100000:])
            except (OSError,subprocess.SubprocessError):pass
            remove(worker)
            if created_builder:
                docker('buildx','rm','--force',builder,timeout=60)
                created_builder=False
            subprocess.run(['docker','volume','rm','-f',volume],capture_output=True,timeout=30)
            subprocess.run(['docker','image','rm','-f',image],capture_output=True,timeout=30)
        except (OSError,RuntimeError,subprocess.SubprocessError):
            reclaimed=False
            BUDGET.quarantine('Package verification cleanup was not confirmed')
            report.update(status='failed',error='Package verification cleanup was not confirmed')
        if lease:BUDGET.release(lease)
        state.atomic_json(output/'package-check.json',report)
        update(progress,'completed' if report['status']=='passed' else 'failed',
               'Exported package verified' if report['status']=='passed' else 'Exported package needs correction',finished_at=utcnow(),resources_reclaimed=reclaimed)
    return {'status':report['status'],'report_path':'/mnt/user-data/'+(output/'package-check.json').relative_to(Path(workspace).resolve()).as_posix(),
            'job_id':job_id,'error':report.get('error','')}
