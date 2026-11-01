#!/usr/bin/env python3
"""Build the exact exported package, run two cycles across container replacement, inspect its BI output."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from righaven import docker_runtime, environment_runtime, state
from unittest.mock import patch


def run(*argv, **kwargs):
    result=subprocess.run(list(argv),capture_output=True,text=True,timeout=kwargs.pop('timeout',900),**kwargs)
    if result.returncode:raise RuntimeError(' '.join(argv[:4])+': '+result.stderr[-6000:]+'\n'+result.stdout[-6000:])
    return result.stdout


def main():
    repo=Path(__file__).resolve().parents[1]
    tag='verified-pipeline:local';container='rh-pipeline-'+uuid.uuid4().hex[:10];volume=container+'-data'
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);root.chmod(0o755);out=root/'output';out.mkdir();out.chmod(0o777)
        with patch.object(state,'STATE',root/'state'),patch.object(docker_runtime,'host_path',lambda p:str(p)),patch.object(environment_runtime,'pinned',return_value=set()):
            image=environment_runtime.ensure(['sqlglot'])
        generator="""import sys,json
from pathlib import Path
sys.path[:0]=['/opt/righaven','/review/scripts']
import pipeline_scaffold
from acceptance_pipeline import MODEL
result=pipeline_scaffold.scaffold(MODEL,Path('/out'),target='postgres',source_dialect='postgres',name='verified',schedule={'ingest':'@hourly','stubs':'@hourly','transform':'@daily','transform_model_cron':'@hourly'})
print(json.dumps(result))
"""
        compose_args=None
        try:
            run('docker','run','--rm','--network=none','--mount','type=bind,src='+str(repo)+',dst=/review,readonly','--mount','type=bind,src='+str(out)+',dst=/out',image['image_id'],
                '/opt/righaven/apps/sqlglot/venv/bin/python','-c',generator)
            run('docker','build','-t',tag,str(out/'package'),timeout=1200)
            run('docker','volume','create',volume)
            def launch():
                run('docker','run','-d','--name',container,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--tmpfs','/tmp:rw,size=512m',
                    '--memory=2048m','--cpus=2','--mount','type=volume,src='+volume+',dst=/data',
                    '-e','PIPELINE_ENV=test','-e','SQLMESH_GATEWAY=local','-e','STUB_ROWS=3','-e','STUB_ROWS_LIMIT=3','-e','RIGHAVEN_SOURCE_DUCKDB=/data/source-stub.duckdb',
                    '-e','RIGHAVEN_WAREHOUSE_DUCKDB=/data/warehouse.duckdb',tag)
            previous=None
            for cycle in (1,2):
                launch();deadline=time.monotonic()+180
                while time.monotonic()<deadline:
                    status=subprocess.run(['docker','exec',container,'cat','/data/last-cycle.json'],capture_output=True,text=True)
                    if status.returncode==0:
                        record=json.loads(status.stdout)
                        if record.get('status')=='failed':raise AssertionError(record)
                        if record.get('status')=='passed' and record.get('started_at')!=previous:break
                    time.sleep(2)
                else:raise AssertionError('Exported package did not complete its cycle')
                previous=record['started_at']
                if cycle==2:
                    run('docker','exec',container,'/opt/ingest/bin/python','/app/ops/orchestrate.py','cycle')
                reports=json.loads(run('docker','exec',container,'cat','/data/reports/results.json'))
                counts={row[0]:row[1] for row in reports[0]['rows']}
                assert set(counts.values())=={cycle*3},counts
                reconciled=run('docker','exec',container,'/opt/transform/bin/python','-c',
                    "import duckdb; c=duckdb.connect('/data/warehouse.duckdb',read_only=True); print(c.execute('SELECT sum(ordine_count) FROM marts.ordine_by_cliente').fetchone()[0])").strip()
                assert reconciled==str(cycle*3),reconciled
                html=run('docker','exec',container,'cat','/data/reports/index.html')
                assert '<table' not in html and 'Business report' in html and 'textContent' in html # tables are rendered from actual saved data
                run('docker','exec',container,'/opt/ingest/bin/python','/app/ops/orchestrate.py','health')
                run('docker','rm','-f',container)
            # Verify updates/deletes and a repeated snapshot using actual source data.
            snapshot_args=['docker','run','--rm','--network=none','--mount','type=volume,src='+volume+',dst=/data',
                '-e','PIPELINE_ENV=test','-e','RIGHAVEN_SOURCE_DUCKDB=/data/source-stub.duckdb','-e','RIGHAVEN_WAREHOUSE_DUCKDB=/data/warehouse.duckdb',tag]
            edit="import duckdb;c=duckdb.connect('/data/source-stub.duckdb');c.execute('DELETE FROM vendite.ordine WHERE id=(SELECT min(id) FROM vendite.ordine)');c.execute('UPDATE vendite.ordine SET importo=87654321 WHERE id=(SELECT min(id) FROM vendite.ordine)')"
            run(*snapshot_args,'/opt/ingest/bin/python','-c',edit)
            for repeat in (1,2):
                run(*snapshot_args,'/opt/ingest/bin/python','/app/ingestion/pipeline.py')
                raw=run(*snapshot_args,'/opt/ingest/bin/python','-c',"import duckdb;c=duckdb.connect('/data/warehouse.duckdb',read_only=True);print(c.execute('SELECT count(*), max(importo) FROM raw.ordine').fetchone())")
                assert '5' in raw and '87654321' in raw,raw
            run(*snapshot_args,'/opt/transform/bin/sqlmesh','-p','/data/transform','--gateway','local','plan','--restate-model','*','--auto-apply','--no-prompts')
            total=run(*snapshot_args,'/opt/transform/bin/python','-c',"import duckdb;c=duckdb.connect('/data/warehouse.duckdb',read_only=True);print(c.execute('SELECT sum(ordine_count) FROM marts.ordine_by_cliente').fetchone()[0])").strip()
            assert total=='5',total
            # Actual source-engine laboratory, using the delivered Compose overlay.
            package=out/'package'
            (package/'.env').write_text((package/'.env.example').read_text().replace('STUB_ROWS=200','STUB_ROWS=3')+'\nSTUB_ROWS_LIMIT=3\n')
            compose_args=['docker','compose','-p',container+'-lab','-f',str(package/'compose.yaml'),'-f',str(package/'compose.lab.yaml')]
            run(*compose_args,'up','-d','--no-build',timeout=300)
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                result=subprocess.run([*compose_args,'exec','-T','pipeline','cat','/data/last-cycle.json'],capture_output=True,text=True)
                if result.returncode==0:
                    record=json.loads(result.stdout)
                    if record['status']=='failed':raise AssertionError(record)
                    if record['status']=='passed':break
                time.sleep(2)
            else:raise AssertionError('Native PostgreSQL source lab did not complete')
            count=run(*compose_args,'exec','-T','source-db','psql','-U','righaven_lab','-d','source_lab','-tAc','SELECT count(*) FROM vendite."Cliente"').strip()
            assert count=='3',count
            print('Exported package OK: clean build, read-only startup, ordered cycles, replacement/restart, durable state, repeatable snapshots, real BI report and actual PostgreSQL source lab')
        except Exception:
            if compose_args:
                diagnostic=subprocess.run([*compose_args,'logs','--tail','70'],capture_output=True,text=True)
                print(diagnostic.stdout[-10000:]+diagnostic.stderr[-2000:],file=sys.stderr)
            logs=subprocess.run(['docker','logs',container],capture_output=True,text=True)
            print(logs.stdout[-8000:]+logs.stderr[-4000:],file=sys.stderr);raise
        finally:
            if compose_args:subprocess.run([*compose_args,'down','-v','--remove-orphans'],capture_output=True)
            subprocess.run(['docker','rm','-f',container],capture_output=True)
            subprocess.run(['docker','volume','rm','-f',volume],capture_output=True)
            subprocess.run(['docker','image','rm','-f',tag],capture_output=True)


if __name__=='__main__':main()
