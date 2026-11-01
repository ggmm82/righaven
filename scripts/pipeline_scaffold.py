"""Production package generated from the schema model (runs in the pinned SQLGlot environment).

Layout: ingestion (dlt), transform (SQLMesh with local and production gateways),
stubs (periodic synthetic data for test environments), ops (supercronic crontab
and job runner), Dockerfile, compose, CI and runbook. Secrets are never written:
every credential is an environment variable listed without value in .env.example.
"""
import json,re,shutil
from pathlib import Path
import pipeline_model as pm

DESTINATIONS={'postgres':'postgres','tsql':'mssql','fabric':'fabric','duckdb':'duckdb'}
SOURCE_DRIVERS={'postgres':('postgresql+psycopg','psycopg[binary]==3.3.6'),'tsql':('mssql+pyodbc','pyodbc==5.3.0'),
                'mysql':('mysql+pymysql','PyMySQL==1.2.3'),'oracle':('oracle+oracledb','oracledb==26.0.1'),'sqlite':('sqlite',None),
                'duckdb':('duckdb',None),'fabric':('mssql+pyodbc','pyodbc==5.3.0')}
DLT='1.31.0';SQLMESH='0.236.4';FAKER='40.43.0';DUCKDB_TRANSFORM='1.5.6'
SUPERCRONIC={'version':'v0.2.50','amd64':'d2d7c97fbfefc763d5bbcbbb3f8d61f9dd3410ce5d05a737c414994b80b8cdd0','arm64':'a1c0af9872e8de89a1ce5c1b596e26c42917d5a2cf914d98faee2e28156899e2'}
CURSOR=re.compile(r'(?i)^(updated|modified|last_?modified|last_?update|changed|data_?modifica|data_?aggiornamento|ultima_?modifica)(_?(at|on|date|time|ts))?$')
CREATED=re.compile(r'(?i)^(created|inserted|data_?inserimento|data_?creazione)(_?(at|on|date|time|ts))?$')
BREAK1=re.compile(r'([^_])([A-Z][a-z]+)');BREAK2=re.compile(r'([a-z0-9])([A-Z])');NON=re.compile(r'[^a-zA-Z0-9_]+')


def snake(name):
    """dlt's default snake_case naming (camelCase splits, symbols to underscores, lower case)."""
    text=BREAK2.sub(r'\1_\2',BREAK1.sub(r'\1_\2',name))
    text=NON.sub('_',text).lower()
    text=re.sub(r'_+','_',text).strip('_') or '_'
    return '_'+text if text[0].isdigit() else text


def plan_tables(model):
    tables=[t for t in model['tables'] if t.get('kind','table')=='table']
    schemas={t['schema'] for t in tables}
    rows=[]
    for t in tables:
        target=snake((t['schema']+'__' if len(schemas)>1 and t['schema'] else '')+t['name'])
        # dlt raises on missing cursor values: only NOT NULL columns qualify.
        candidates=[c for c in t['columns'] if not c['nullable']]
        cursor=next((c['name'] for c in candidates if CURSOR.match(c['name'])),None)
        cursor_type=next((c['type'] for c in t['columns'] if c['name']==cursor),None)
        if cursor and not re.match(r'(?i)(TIMESTAMP|DATE|DATETIME|INT|BIGINT)',cursor_type or ''):cursor=None
        rows.append({'schema':t['schema'],'name':t['name'],'target':target,'primary_key':list(t['primary_key']),'cursor':cursor,
                     'write_disposition':'replace', 'cursor_confirmed':False, 'candidate_cursor':cursor,
                     'columns':[{'name':c['name'],'target':snake(c['name']),'type':c['type'],'nullable':c['nullable'],'pii':bool(c.get('pii'))} for c in t['columns']]})
    return rows


def duck_type(text):
    from sqlglot import exp
    rendered=exp.DataType.build(text).sql(dialect='duckdb')
    return re.sub(r'^TEXT\(.*\)$','TEXT',rendered)


def write(root,relative,text,mode=None):
    path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    if mode:path.chmod(mode)
    return path


PIPELINE='''"""Scheduled acquisition with dlt: source database -> warehouse "raw" dataset.

PIPELINE_ENV selects the environment:
  local/test  source = DuckDB file with stub data (RIGHAVEN_SOURCE_DUCKDB), destination = local DuckDB (RIGHAVEN_WAREHOUSE_DUCKDB)
  prod        source = SOURCES__SQL_DATABASE__CREDENTIALS, destination = DESTINATION_TYPE with DESTINATION__<TYPE>__CREDENTIALS
Tables, keys and incremental cursors are listed in tables.json (generated from the schema model; edit there).
"""
import json,os
from pathlib import Path

import dlt

HERE=Path(__file__).resolve().parent
TABLES=json.loads((HERE/'tables.json').read_text())
ENV=os.environ.get('PIPELINE_ENV','prod')
DATASET=os.environ.get('DESTINATION_DATASET','raw')
STORAGE='v1.4.0'  # readable by the DuckDB versions of dlt and SQLMesh


def local_resources(path):
    import duckdb
    def reader(table):
        name=('"'+table['schema']+'".' if table['schema'] else '')+'"'+table['name']+'"'
        cursor=dlt.sources.incremental(table['cursor']) if table.get('cursor') and table.get('cursor_confirmed') else None
        @dlt.resource(name=table['target'],primary_key=table['primary_key'] or None,write_disposition=table['write_disposition'])
        def rows(updated=cursor):
            con=duckdb.connect(path,read_only=True)
            try:
                result=con.execute('SELECT * FROM '+name)
                columns=[d[0] for d in result.description]
                while batch:=result.fetchmany(5000):
                    yield [dict(zip(columns,row)) for row in batch]
            finally:con.close()
        return rows
    return [reader(t) for t in TABLES]


def production_resources():
    from dlt.sources.sql_database import sql_table
    resources=[]
    for t in TABLES:
        resource=sql_table(table=t['name'],schema=t['schema'] or None,
                           incremental=dlt.sources.incremental(t['cursor']) if t.get('cursor') and t.get('cursor_confirmed') else None,
                           primary_key=t['primary_key'] or None,write_disposition=t['write_disposition'])
        resources.append(resource.with_name(t['target']))
    return resources


def destination():
    if ENV in ('local','test'):
        import duckdb
        path=os.environ.get('RIGHAVEN_WAREHOUSE_DUCKDB','warehouse.duckdb')
        if not Path(path).exists():
            con=duckdb.connect();con.execute("ATTACH '"+path.replace("'","''")+"' AS w (STORAGE_VERSION '"+STORAGE+"')");con.close()
        return dlt.destinations.duckdb(path)
    return os.environ['DESTINATION_TYPE']


def main():
    if ENV in ('local','test'):resources=local_resources(os.environ['RIGHAVEN_SOURCE_DUCKDB'])
    elif ENV=='prod':resources=production_resources()
    else:raise SystemExit('PIPELINE_ENV must be local, test or prod')
    pipeline=dlt.pipeline(pipeline_name=(os.environ.get('PIPELINE_NAME') or '{name}_ingestion'),destination=destination(),dataset_name=DATASET,
                          pipelines_dir=os.environ.get('DLT_PIPELINES_DIR'))
    info=pipeline.run(resources)
    print(info)
    if info.has_failed_jobs:raise SystemExit('Load completed with failed jobs')


if __name__=='__main__':
    main()
'''

ENTRYPOINT_SH='''#!/bin/sh
set -eu
case "${1:-schedule}" in
 schedule)
   /opt/ingest/bin/python /app/ops/orchestrate.py init
   /opt/ingest/bin/python /app/ops/orchestrate.py tick
   exec /usr/local/bin/supercronic -passthrough-logs /app/ops/crontab
   ;;
 init|cycle|tick|report|health) exec /opt/ingest/bin/python /app/ops/orchestrate.py "$@" ;;
 *) exec "$@" ;;
esac
'''

RUN_SH='''#!/bin/sh
# Job runner for supercronic: one job at a time per name, explicit exit codes, logs on stdout/stderr.
set -eu
job="${1:?usage: run.sh ingest|transform|stubs|deploy}"
env="${PIPELINE_ENV:-prod}"
app="${APP_DIR:-/app}"
data="${DATA_DIR:-/data}"
lock="${data}/.lock-${job}"
exec 9>"${lock}"
if ! flock -n 9; then
  echo "job ${job}: previous run still active, skipped"
  exit 0
fi
echo "job ${job}: start env=${env} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
case "${job}" in
  ingest)
    /opt/ingest/bin/python "${app}/ingestion/pipeline.py"
    ;;
  transform)
    cd "${data}/transform"
    /opt/transform/bin/sqlmesh --gateway "${SQLMESH_GATEWAY:-prod}" run
    ;;
  deploy)
    cd "${data}/transform"
    /opt/transform/bin/sqlmesh --gateway "${SQLMESH_GATEWAY:-prod}" plan --auto-apply --no-prompts
    ;;
  stubs)
    if [ "${env}" = "prod" ]; then
      echo "job stubs: disabled in production"
      exit 0
    fi
    /opt/ingest/bin/python "${app}/stubs/stubgen.py" --model "${app}/schema/model.json" \\
      --output "${data}/stubs" --database "${RIGHAVEN_SOURCE_DUCKDB:?}" --rows "${STUB_ROWS:-200}"
    ;;
  *)
    echo "unknown job: ${job}" >&2
    exit 2
    ;;
esac
echo "job ${job}: done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
'''

INIT_SH='''#!/bin/sh
# Test environment bootstrap: empty replica of the source schema, ready for stub batches.
set -eu
app="${APP_DIR:-/app}"
target="${RIGHAVEN_SOURCE_DUCKDB:?}"
if [ -f "${target}" ]; then
  echo "replica already present: ${target}"
  exit 0
fi
/opt/ingest/bin/python - "${target}" "${app}/schema/replica.duckdb.sql" <<'PY'
import sys
import duckdb
target, ddl = sys.argv[1], sys.argv[2]
con = duckdb.connect()
con.execute("ATTACH '" + target.replace("'", "''") + "' AS replica (STORAGE_VERSION 'v1.4.0')")
con.execute("USE replica")
con.execute(open(ddl).read())
con.close()
print("replica created: " + target)
PY
'''


def dockerfile(target, source_dialect=None):
    odbc=''
    if target in ('tsql','fabric') or source_dialect in ('tsql','fabric'):
        odbc='''
# Microsoft ODBC Driver 18 for SQL Server / Fabric Warehouse (signed Microsoft repository).
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \\
 && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \\
 && apt-get update \\
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18=18.* unixodbc=2.3.* \\
 && rm -rf /var/lib/apt/lists/*
'''
    return f'''# syntax=docker/dockerfile:1
# Pin the base image by digest before release: docker buildx imagetools inspect python:3.11-slim-bookworm
FROM python:3.11-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG TARGETARCH
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_DIR=/app DATA_DIR=/data

RUN apt-get update \\
 && apt-get install -y --no-install-recommends ca-certificates=* curl=7.* gnupg=2.* util-linux=2.* \\
 && rm -rf /var/lib/apt/lists/*
{odbc}
# supercronic {SUPERCRONIC['version']}: cron for containers, verified by SHA-256.
RUN set -eu; \\
    case "${{TARGETARCH:-amd64}}" in \\
      amd64) sum={SUPERCRONIC['amd64']} ;; \\
      arm64) sum={SUPERCRONIC['arm64']} ;; \\
      *) echo "unsupported architecture" >&2; exit 1 ;; \\
    esac; \\
    curl -fsSLo /usr/local/bin/supercronic "https://github.com/aptible/supercronic/releases/download/{SUPERCRONIC['version']}/supercronic-linux-${{TARGETARCH:-amd64}}"; \\
    echo "${{sum}}  /usr/local/bin/supercronic" | sha256sum -c -; \\
    chmod 0755 /usr/local/bin/supercronic

# Two environments: dlt and SQLMesh pin different DuckDB versions. Locks carry hashes (see README).
COPY ingestion/requirements.lock /tmp/ingest.lock
COPY transform/requirements.lock /tmp/transform.lock
RUN python -m venv /opt/ingest && /opt/ingest/bin/pip install --no-cache-dir --require-hashes -r /tmp/ingest.lock \\
 && python -m venv /opt/transform && /opt/transform/bin/pip install --no-cache-dir --require-hashes -r /tmp/transform.lock \\
 && rm /tmp/ingest.lock /tmp/transform.lock

RUN useradd --system --uid 10001 --home-dir /data --shell /usr/sbin/nologin pipeline && mkdir -p /data && chown pipeline /data
COPY --chown=root:root . /app
RUN chmod 0755 /app/ops/run.sh /app/ops/init-test.sh /app/ops/entrypoint.sh

USER pipeline
WORKDIR /data
HEALTHCHECK --interval=5m --start-period=10m --timeout=10s CMD ["/opt/ingest/bin/python", "/app/ops/orchestrate.py", "health"]
ENTRYPOINT ["/app/ops/entrypoint.sh"]
CMD ["schedule"]
'''


def compose(name):
    return f'''# docker compose up -d  (see README for the environment variables)
services:
  pipeline:
    build: .
    image: {name}-pipeline:local
    restart: unless-stopped
    env_file: .env
    volumes:
      - pipeline-data:/data
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
  reports:
    profiles: [reports]
    image: {name}-pipeline:local
    entrypoint: [/opt/transform/bin/python, -m, http.server, "8080", --directory, /data/reports]
    ports: ["127.0.0.1:8080:8080"]
    volumes: [pipeline-data:/data:ro]
    read_only: true
    tmpfs: [/tmp]
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
volumes:
  pipeline-data:
'''


def env_example(target,source_dialect):
    dest=DESTINATIONS[target].upper()
    lines=['# Copy to .env and fill in; never commit .env.','# Environment: test runs stub generation and a local DuckDB warehouse; prod uses the systems below.',
           'PIPELINE_ENV=test','PIPELINE_NAME=project_ingestion','DESTINATION_DATASET=raw','SQLMESH_GATEWAY=local','STUB_ROWS=200',
           'RIGHAVEN_SOURCE_DUCKDB=/data/source-stub.duckdb','RIGHAVEN_WAREHOUSE_DUCKDB=/data/warehouse.duckdb','',
           '# Production source (read-only account), SQLAlchemy URL for dlt sql_database:',
           'SOURCES__SQL_DATABASE__CREDENTIALS=','',
           '# Production destination for dlt:','DESTINATION_TYPE='+DESTINATIONS[target],
           'DESTINATION__'+dest+'__CREDENTIALS=','',
           '# Production warehouse for SQLMesh (gateway prod):','# WAREHOUSE_HOST=','# WAREHOUSE_PORT=','# WAREHOUSE_DATABASE=','# WAREHOUSE_USER=','# WAREHOUSE_PASSWORD=']
    if target=='fabric':lines+=['# Fabric: service principal for the Warehouse SQL endpoint','FABRIC_TENANT_ID=','FABRIC_CLIENT_ID=','FABRIC_CLIENT_SECRET=']
    return '\n'.join(lines)+'\n'


def sqlmesh_config(target,name,cron):
    prod={
     'postgres':"""    connection:
      type: postgres
      host: "{{ env_var('WAREHOUSE_HOST', 'localhost') }}"
      port: "{{ env_var('WAREHOUSE_PORT', '5432') }}"
      database: "{{ env_var('WAREHOUSE_DATABASE', 'warehouse') }}"
      user: "{{ env_var('WAREHOUSE_USER', 'sqlmesh') }}"
      password: "{{ env_var('WAREHOUSE_PASSWORD', '') }}"
""",
     'tsql':"""    connection:
      type: mssql
      driver: pyodbc
      host: "{{ env_var('WAREHOUSE_HOST', 'localhost') }}"
      port: "{{ env_var('WAREHOUSE_PORT', '1433') }}"
      database: "{{ env_var('WAREHOUSE_DATABASE', 'warehouse') }}"
      user: "{{ env_var('WAREHOUSE_USER', 'sqlmesh') }}"
      password: "{{ env_var('WAREHOUSE_PASSWORD', '') }}"
""",
     'fabric':"""    connection:
      type: fabric
      host: "{{ env_var('WAREHOUSE_HOST', 'example.datawarehouse.fabric.microsoft.com') }}"
      database: "{{ env_var('WAREHOUSE_DATABASE', 'warehouse') }}"
      user: "{{ env_var('FABRIC_CLIENT_ID', '') }}"
      password: "{{ env_var('FABRIC_CLIENT_SECRET', '') }}"
      tenant_id: "{{ env_var('FABRIC_TENANT_ID', '') }}"
""",
     'duckdb':"""    connection:
      type: duckdb
      database: "{{ env_var('WAREHOUSE_PATH', '/data/warehouse-prod.duckdb') }}"
"""}[target]
    return f'''# SQLMesh project: "local" runs on the DuckDB warehouse filled by the ingestion test; "prod" is the production warehouse.
gateways:
  local:
    connection:
      type: duckdb
      database: "{{ env_var('RIGHAVEN_WAREHOUSE_DUCKDB', '/data/warehouse.duckdb') }}"
  prod:
{prod}default_gateway: local
model_defaults:
  dialect: duckdb
  start: '2026-01-01'
  cron: '{cron}'
'''


def staging_model(table):
    pk=[snake(c) for c in table['primary_key']]
    audits=''
    if pk:audits=',\n  audits (\n    not_null(columns := ('+', '.join(pk)+')),\n    unique_combination_of_columns(columns := ('+', '.join(pk)+'))\n  )'
    grain='\n  grain ('+', '.join(pk)+'),' if pk else ''
    columns=',\n  '.join(c['target'] for c in table['columns'])
    return f'''MODEL (
  name staging.stg_{table['target']},
  kind VIEW,{grain}
  description 'Source {(table['schema']+'.' if table['schema'] else '')+table['name']} as loaded by dlt (raw.{table['target']}).'{audits}
);

SELECT
  {columns},
  _dlt_load_id
FROM raw.{table['target']}
'''


def example_mart(model,tables):
    by_name={(t['schema'].lower(),t['name'].lower()):t for t in tables}
    for t in model['tables']:
        for fk in t['foreign_keys']:
            child=by_name.get((t['schema'].lower(),t['name'].lower()));parent=by_name.get(((fk['references'].get('schema') or '').lower(),fk['references']['table'].lower()))
            if not child or not parent or child is parent or not parent['primary_key'] or len(fk['columns'])!=1:continue
            pk=snake(parent['primary_key'][0]);fk_col=snake(fk['columns'][0])
            name=f"{child['target']}_by_{parent['target']}"
            return name,f'''MODEL (
  name marts.{name},
  kind FULL,
  grain ({pk}),
  description 'Example mart: number of {child['target']} rows for each {parent['target']}. Replace with the business measures agreed in the catalog.',
  audits (
    not_null(columns := ({pk})),
    unique_values(columns := ({pk}))
  )
);

SELECT
  p.{pk},
  COUNT(c.{fk_col}) AS {child['target']}_count
FROM staging.stg_{parent['target']} AS p
LEFT JOIN staging.stg_{child['target']} AS c
  ON c.{fk_col} = p.{pk}
GROUP BY p.{pk}
'''
    return None,None


def external_models(tables):
    lines=[]
    for t in tables:
        lines.append('- name: raw.'+t['target'])
        lines.append('  columns:')
        for c in t['columns']:lines.append('    '+c['target']+': '+duck_type(c['type']))
        lines.append('    _dlt_load_id: TEXT')
        lines.append('    _dlt_id: TEXT')
    return '\n'.join(lines)+'\n'


CI='''name: pipeline

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  checks:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Environments from hashed locks
        run: |
          python -m venv /tmp/ingest && /tmp/ingest/bin/pip install --require-hashes -r ingestion/requirements.lock
          python -m venv /tmp/transform && /tmp/transform/bin/pip install --require-hashes -r transform/requirements.lock
      - name: End-to-end test on stub data (no production system)
        env:
          PIPELINE_ENV: test
          RIGHAVEN_SOURCE_DUCKDB: ${{ runner.temp }}/source-stub.duckdb
          RIGHAVEN_WAREHOUSE_DUCKDB: ${{ github.workspace }}/transform/warehouse.duckdb
        run: |
          /tmp/ingest/bin/python - "$RIGHAVEN_SOURCE_DUCKDB" schema/replica.duckdb.sql <<'PY'
          import sys, duckdb
          con = duckdb.connect()
          con.execute("ATTACH '" + sys.argv[1] + "' AS r (STORAGE_VERSION 'v1.4.0')")
          con.execute("USE r")
          con.execute(open(sys.argv[2]).read())
          PY
          /tmp/ingest/bin/python stubs/stubgen.py --model schema/model.json --output "$RUNNER_TEMP/stubs" --database "$RIGHAVEN_SOURCE_DUCKDB" --batch 0
          /tmp/ingest/bin/python stubs/stubgen.py --model schema/model.json --output "$RUNNER_TEMP/stubs" --database "$RIGHAVEN_SOURCE_DUCKDB" --batch 1
          /tmp/ingest/bin/python ingestion/pipeline.py
          cd transform && /tmp/transform/bin/sqlmesh --gateway local plan --auto-apply --no-prompts
'''


def readme(model,target,source_dialect,tables,schedule,mart):
    pii=[t['target']+'.'+c['target'] for t in tables for c in t['columns'] if c['pii']]
    rows=''.join(f"| `{(t['schema']+'.' if t['schema'] else '')+t['name']}` | `raw.{t['target']}` | {', '.join(t['primary_key']) or '—'} | {t['cursor'] or 'full reload'} | {t['write_disposition']} |\n" for t in tables)
    jobs=''.join(f"| `{k}` | `{v}` |\n" for k,v in schedule.items())
    return f'''# {model['name']}: data pipeline

Generated by RigHaven from the schema model `schema/model.json` ({len(tables)} tables, source dialect `{source_dialect}`, production warehouse `{target}`).
Hashed dependencies are included. Acceptance is determined by the delivered verification report, not by this generated document.

## Flow

1. **Source** (read-only account) → **dlt** (`ingestion/pipeline.py`, tables and cursors in `ingestion/tables.json`) → dataset `raw` in the warehouse.
2. **SQLMesh** (`transform/`): `staging.stg_*` views with key audits, then `marts.*` business tables{' (example: `marts.'+mart+'`)' if mart else ''}.
3. **BI**: your existing tool (Power BI, Metabase, Superset, ...) reads the `marts` schema of the production warehouse.
4. **Test environment**: `ops/init-test.sh` creates the empty replica (`schema/replica.duckdb.sql`) and the `stubs` job adds a synthetic batch on every run (`stubs/stubgen.py`, deterministic, foreign-key consistent).

## Tables

| Source | Raw table | Primary key | Incremental cursor | Load |
|---|---|---|---|---|
{rows}
Personal data columns (always synthetic in test): {', '.join('`'+p+'`' for p in pii) or 'none declared'}.

## Schedule (`ops/crontab`, supercronic)

| Job | Cron |
|---|---|
{jobs}
`ops/run.sh` takes a lock per job (a slow run is skipped, not overlapped) and exits non-zero on failure. `deploy` applies SQLMesh model changes to production and is run once per release, not on a schedule.

## First run

```bash
cp .env.example .env            # fill in values; .env is never committed
docker compose build
docker compose run --rm pipeline cycle
docker compose run --rm pipeline cycle   # proves repeatability
docker compose run --rm pipeline health
docker compose up -d
```

For production set `PIPELINE_ENV=prod`, `SQLMESH_GATEWAY=prod`, the source and destination credentials, run `deploy` once and start the service.
Pin the base image by digest and keep the lock files committed.

## Required checks before delivery

The verification report must record actual evidence for clean start, two cycles, restart, source counts, agreed KPIs, report opening and editable source portability. Do not mark these passed solely because this package was generated.
Not performed: connection to the real source and warehouse, production volumes and timings, BI reports.

## Microsoft Fabric

`fabric/README.md` describes the Fabric variant (dlt `fabric` destination, SQLMesh `fabric` gateway, `fabric-cicd` for workspace items).
'''


FABRIC='''# Microsoft Fabric variant

- **Ingestion**: dlt destination `fabric` writes the `raw` dataset into a Fabric Warehouse through its SQL endpoint
  (`DESTINATION_TYPE=fabric`, `DESTINATION__FABRIC__CREDENTIALS`, ODBC Driver 18 in the image).
- **Transformation**: SQLMesh gateway `prod` with `type: fabric` (service principal from `FABRIC_TENANT_ID`,
  `FABRIC_CLIENT_ID`, `FABRIC_CLIENT_SECRET`). Fabric Warehouse does not enforce primary and foreign keys: the SQLMesh audits are the checks.
  Check in the SQLMesh documentation for your version whether a separate `state_connection` is recommended.
- **Scheduling**: this container can run anywhere with network access to the Warehouse. Alternatively schedule the same
  commands from a Fabric Data Pipeline or notebook.
- **Workspace items** (semantic model, Power BI report, notebooks) are deployed from Git with Microsoft's
  [`fabric-cicd`](https://github.com/microsoft/fabric-cicd) library; keep them in a `workspace/` folder in the Fabric Git format.

None of this has been executed against a Fabric tenant by RigHaven: test it in a non-production workspace first.
'''


def requirements(target,source_dialect):
    driver=SOURCE_DRIVERS.get(source_dialect,(None,None))[1]
    extra={'postgres':'postgres','tsql':'mssql','fabric':'fabric','duckdb':'duckdb'}[target]
    ingest=[f'dlt[{extra},sql-database]=={DLT}',f'Faker=={FAKER}']+([driver] if driver else [])
    engine={'postgres':'[postgres]','tsql':'[mssql-odbc]','fabric':'[fabric]','duckdb':''}[target]
    transform=[f'sqlmesh{engine}=={SQLMESH}',f'duckdb=={DUCKDB_TRANSFORM}']
    header='# Exact top-level pins; generate the hashed lock with:  uv pip compile --generate-hashes {} -o {}\n'
    return (header.format('ingestion/requirements.in','ingestion/requirements.lock')+'\n'.join(ingest)+'\n',
            header.format('transform/requirements.in','transform/requirements.lock')+'\n'.join(transform)+'\n')


def scaffold(model,output,*,target,source_dialect,name,schedule,stub_source=None):
    if target not in DESTINATIONS:raise ValueError('Destinazione tra '+', '.join(DESTINATIONS))
    name=re.sub(r'[^a-z0-9_]','_',(name or model['name']).lower()).strip('_') or 'pipeline'
    root=output/'package';root.mkdir()
    tables=plan_tables(model)
    write(root,'schema/model.json',json.dumps(model,indent=2,ensure_ascii=False))
    replica,limits=pm.ddl(model,'duckdb');write(root,'schema/replica.duckdb.sql',replica)
    pm.verify_ddl(replica,'duckdb')
    if target!='duckdb':
        warehouse,warehouse_limits=pm.ddl(model,target);write(root,'schema/source-structure.'+target+'.sql',warehouse);limits+=warehouse_limits
    write(root,'ingestion/tables.json',json.dumps([{k:v for k,v in t.items() if k!='columns'} for t in tables],indent=2,ensure_ascii=False))
    write(root,'ingestion/pipeline.py',PIPELINE.replace('{name}',name))
    ingest,transform=requirements(target,source_dialect)
    write(root,'ingestion/requirements.in',ingest);write(root,'transform/requirements.in',transform)
    lock_root=Path(__file__).resolve().parents[1]/'config/toolkit/pipeline'
    if not lock_root.exists():lock_root=None
    for env,source in [('ingestion','ingest'),('transform','transform')]:
        shutil.copyfile(lock_root/(source+'.lock') if lock_root else Path(__file__).with_name('package-'+source+'.lock'),root/env/'requirements.lock')
    write(root,'transform/config.yaml',sqlmesh_config(target,name,schedule['transform_model_cron']))
    write(root,'transform/external_models.yaml',external_models(tables))
    for t in tables:write(root,'transform/models/staging/stg_'+t['target']+'.sql',staging_model(t))
    mart,body=example_mart(model,tables)
    if mart:write(root,'transform/models/marts/'+mart+'.sql',body)
    write(root,'transform/models/marts/README.md','# Marts\n\nBusiness tables read by the BI tool. Each model declares grain, description and audits; keep the measures consistent with the catalog.\n')
    (root/'stubs').mkdir();shutil.copy2(Path(__file__).resolve().parent/'stubgen.py',root/'stubs'/'stubgen.py')
    crontab=('# One ordered cycle; ingestion and transformation never overlap shared storage.\n'
             "* * * * * /opt/ingest/bin/python /app/ops/orchestrate.py tick\n")
    write(root,'ops/crontab',crontab)
    write(root,'ops/schedules.json',json.dumps({k:schedule[k] for k in ('stubs','ingest','transform')},indent=2))
    write(root,'ops/run.sh',RUN_SH,0o755);write(root,'ops/init-test.sh',INIT_SH,0o755)
    write(root,'ops/entrypoint.sh',ENTRYPOINT_SH,0o755)
    shutil.copyfile(Path(__file__).with_name('pipeline_runtime.py'),root/'ops/orchestrate.py')
    write(root,'reporting/metrics.json',json.dumps([{'title':'Example: source row counts — replace with agreed business KPIs','sql':' UNION ALL '.join("SELECT '"+t['target']+"' AS source, count(*) AS rows FROM raw."+t['target'] for t in tables)}],indent=2))
    write(root,'reporting/README.md','Define agreed business measures in metrics.json. Example counts are not an accepted business report. The runtime saves an offline interactive HTML report and its query results. Production BI uses the configured warehouse; remote report adapters must be configured and tested separately.\n')
    write(root,'Dockerfile',dockerfile(target,source_dialect));write(root,'compose.yaml',compose(name));write(root,'.env.example',env_example(target,source_dialect))
    write(root,'.dockerignore','.env\n**/__pycache__\n*.duckdb\n.git\n')
    write(root,'.gitignore','.env\n*.duckdb\n*.duckdb.wal\n__pycache__/\n.cache/\nlogs/\n')
    write(root,'.github/workflows/pipeline.yml',CI)
    write(root,'fabric/README.md',FABRIC)
    write(root,'README.md',readme(model,target,source_dialect,tables,{'stubs':schedule['stubs'],'ingest':schedule['ingest'],'transform':schedule['transform']},mart))
    files=sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
    return {'package':'package','name':name,'target':target,'tables':len(tables),'staging_models':len(tables),'example_mart':mart,
            'incremental_tables':[t['target'] for t in tables if t['cursor']],'files':files,'limits':limits+[
            'Local replica is a DuckDB simulation. Source-engine parity must be tested separately.',
            'Example report counts must be replaced with approved business KPIs.',
            'Il pacchetto non è stato eseguito contro la sorgente e il warehouse reali.']}
