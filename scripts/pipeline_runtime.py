"""Standalone exported project runtime: ordered cycles, durable state, business reports.

No RigHaven import. Run from the delivered package, with a writable DATA_DIR.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def paths():
    root = Path(os.environ.get('APP_DIR', Path(__file__).resolve().parents[1]))
    data = Path(os.environ.get('DATA_DIR', '/data'))
    data.mkdir(parents=True, exist_ok=True)
    return root, data


def command(argv, cwd=None):
    started = time.monotonic()
    result = subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True, text=True, timeout=1800)
    print(result.stdout[-8000:])
    if result.returncode:
        # Provider credentials never enter command-line arguments. Scrub configured secrets in failures.
        error = result.stderr[-4000:]
        for key, value in os.environ.items():
            if value and len(value) > 4 and any(k in key.upper() for k in ('PASSWORD', 'SECRET', 'TOKEN', 'CREDENTIALS')):
                error = error.replace(value, '[REDACTED]')
        raise RuntimeError('Command failed: ' + Path(str(argv[0])).name + '\n' + error)
    return {'program': Path(str(argv[0])).name, 'seconds': round(time.monotonic() - started, 3), 'returncode': 0}


def init(root, data):
    import duckdb
    source = Path(os.environ.get('RIGHAVEN_SOURCE_DUCKDB', str(data / 'source-stub.duckdb')))
    if os.environ.get('PIPELINE_ENV', 'test') != 'prod' and not source.exists():
        with duckdb.connect() as con:
            con.execute("ATTACH '" + str(source).replace("'", "''") + "' AS source (STORAGE_VERSION 'v1.4.0')")
            con.execute('USE source')
            con.execute((root / 'schema/replica.duckdb.sql').read_text())
    project = data / 'transform'
    # Application source is immutable; SQLMesh state/logs/cache belong in the data volume.
    for path in (root / 'transform').rglob('*'):
        if path.is_file():
            target = project / path.relative_to(root / 'transform')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
                shutil.copyfile(path, target)
    return project


def render(root, data):
    """Render actual saved query results into a portable interactive report; no network or CDN."""
    import duckdb
    definitions = json.loads((root / 'reporting/metrics.json').read_text())
    if not definitions:
        raise ValueError('Define the business measures before reporting')
    warehouse = os.environ.get('RIGHAVEN_WAREHOUSE_DUCKDB', str(data / 'warehouse.duckdb'))
    reports = []
    with duckdb.connect(warehouse, read_only=True) as con:
        for metric in definitions:
            # A read-only database also prevents mutating SQL; disallow external input readers.
            sql = metric['sql']
            import re
            if not re.match(r'^\s*(SELECT|WITH)\b', sql, re.I) or re.search(r'\b(read_\w+|attach|copy|install|load)\s*\(?', sql, re.I):
                raise ValueError('Reports require a read-only warehouse SELECT')
            result = con.execute(sql)
            rows = result.fetchmany(10001)
            if len(rows) > 10000:
                raise ValueError('Aggregate the BI query to at most 10000 rows')
            reports.append({'title': metric['title'], 'columns': [c[0] for c in result.description], 'rows': rows})
    folder = data / 'reports'; folder.mkdir(exist_ok=True)
    # Script data is escaped against closing tags; user content is inserted using textContent.
    payload = json.dumps(reports, default=str).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Business report</title>
<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.5rem;border-bottom:1px solid #ccc}section{margin:2rem 0;overflow:auto}input{padding:.6rem;width:90%}button{padding:.5rem;cursor:pointer}</style>
<h1>Business report</h1><label>Filter rows <input id="filter" type="search"></label><main id="reports"></main>
<script id="data" type="application/json">PAYLOAD</script><script>
const reports=JSON.parse(document.querySelector('#data').textContent);const host=document.querySelector('#reports');
function paint(){host.replaceChildren();for(const r of reports){const s=document.createElement('section'),h=document.createElement('h2');h.textContent=r.title;s.append(h);const table=document.createElement('table'),head=document.createElement('tr');for(let i=0;i<r.columns.length;i++){const th=document.createElement('th'),b=document.createElement('button');b.textContent=r.columns[i];b.onclick=()=>{r.rows.sort((a,b)=>String(a[i]).localeCompare(String(b[i]),undefined,{numeric:true}));paint()};th.append(b);head.append(th)}table.append(head);for(const row of r.rows.filter(v=>v.join(' ').toLowerCase().includes(document.querySelector('#filter').value.toLowerCase()))){const tr=document.createElement('tr');for(const value of row){const td=document.createElement('td');td.textContent=value??'';tr.append(td)}table.append(tr)}s.append(table);host.append(s)}}document.querySelector('#filter').oninput=paint;paint();
</script></html>'''.replace('PAYLOAD', payload)
    (folder / 'index.html').write_text(page)
    (folder / 'results.json').write_text(json.dumps(reports, default=str, indent=2))
    return {'reports': len(reports), 'rows': sum(len(r['rows']) for r in reports)}


@contextmanager
def cycle_lock(data):
    with (data / '.pipeline.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init', 'cycle', 'tick', 'report', 'health'])
    args = parser.parse_args()
    root, data = paths()
    if args.action == 'health':
        state = json.loads((data / 'last-cycle.json').read_text())
        if state['status'] != 'passed':
            raise SystemExit(1)
        return
    with cycle_lock(data):
        project = init(root, data)
        if args.action == 'init':
            return
        if args.action == 'report':
            print(json.dumps(render(root, data))); return
        state = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'operations': []}
        status = data / 'last-cycle.json'
        def save():
            temp = status.with_suffix('.tmp'); temp.write_text(json.dumps(state, indent=2)); temp.replace(status)
        save()
        try:
            ingest = os.environ.get('INGEST_PYTHON', '/opt/ingest/bin/python')
            sqlmesh = os.environ.get('SQLMESH_BIN', '/opt/transform/bin/sqlmesh')
            timing=data/'schedule-state.json'
            last=json.loads(timing.read_text()) if timing.exists() else {}
            schedules=json.loads((root/'ops/schedules.json').read_text())
            def due(kind):
                if args.action=='cycle' or kind not in last:return True
                from croniter import croniter
                return croniter(schedules[kind],last[kind]).get_next(float)<=time.time()
            def finished(kind):
                last[kind]=time.time();temporary=timing.with_suffix('.tmp');temporary.write_text(json.dumps(last));temporary.replace(timing)
            if due('stubs') and os.environ.get('PIPELINE_ENV', 'test') != 'prod':
                state['operations'].append(command([ingest, root / 'stubs/stubgen.py', '--model', root / 'schema/model.json',
                    '--output', data / 'stubs', '--database', os.environ['RIGHAVEN_SOURCE_DUCKDB'], '--rows', os.environ.get('STUB_ROWS', '200')]))
                finished('stubs')
            if due('ingest'):
                if os.environ.get('PIPELINE_ENV')=='lab':
                    state['operations'].append(command([ingest, root/'ops/seed-source.py']))
                state['operations'].append(command([ingest, root / 'ingestion/pipeline.py']))
                finished('ingest')
            # Plan on first boot or changed application source; run intervals on every cycle.
            config_hash = hashlib.sha256(b''.join(p.read_bytes() for p in sorted((root / 'transform').rglob('*')) if p.is_file())).hexdigest()
            applied = data / 'applied-models'
            gateway = os.environ.get('SQLMESH_GATEWAY', 'local')
            if not applied.exists() or applied.read_text() != config_hash:
                state['operations'].append(command([sqlmesh, '--gateway', gateway, 'plan', '--auto-apply', '--no-prompts'], project))
                applied.write_text(config_hash)
            if due('transform'):
                state['operations'].append(command([sqlmesh, '--gateway', gateway, 'run'], project))
                if os.environ.get('PIPELINE_ENV', 'test') != 'prod':
                    state['report'] = render(root, data)
                finished('transform')
            state['status'] = 'passed'
        except Exception as error:
            state.update(status='failed', error=str(error))
            raise
        finally:
            state['finished_at'] = datetime.now(timezone.utc).isoformat(); save()


if __name__ == '__main__':
    main()
