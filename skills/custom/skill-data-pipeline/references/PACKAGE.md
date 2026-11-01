# Production package (`sqlglot.scaffold`)

```
package/
  README.md                     runbook: flow, tables, schedule, first run, checks done and not done
  schema/model.json             the model; replica.duckdb.sql; source-structure.<target>.sql
  ingestion/pipeline.py         dlt: PIPELINE_ENV local|test -> stub DuckDB source, prod -> sql_database
  ingestion/tables.json         per table: target name (dlt snake_case), primary key, cursor, write disposition
  ingestion/requirements.in     exact top-level pins (dlt extras for the warehouse, source driver, Faker)
  transform/config.yaml         SQLMesh gateways: local (DuckDB) and prod (postgres | mssql | fabric | duckdb) from env_var()
  transform/external_models.yaml  raw.* column types
  transform/models/staging/     one VIEW per source table with not_null/unique audits on the key
  transform/models/marts/       business tables for the BI tool (an example join mart is generated)
  transform/requirements.in     sqlmesh with the engine extra, duckdb 1.5.6
  stubs/stubgen.py              periodic synthetic batches for the test environment
  ops/crontab                   supercronic schedule: stubs, ingest, transform
  ops/run.sh                    locked job runner: ingest | transform | stubs | deploy
  ops/init-test.sh              empty replica for the test environment
  Dockerfile, compose.yaml      non-root, read-only root filesystem, supercronic verified by SHA-256
  .env.example                  every variable, no values
  .github/workflows/pipeline.yml  end-to-end test on stub data in CI
  fabric/README.md              Microsoft Fabric variant and fabric-cicd
```

## Release steps for the user (listed in the delivery, not performed by RigHaven)

1. Generate the hashed locks (`uv pip compile --generate-hashes ...`) and pin the base image digest.
2. Create read-only source credentials and warehouse credentials; fill `.env` outside version control.
3. Run `init-test.sh`, `run.sh stubs`, `run.sh ingest`, `run.sh deploy` in the test environment; review row counts and audits.
4. Switch to `PIPELINE_ENV=prod`, `SQLMESH_GATEWAY=prod`, run `deploy` once, start the service.
5. Point the BI tool (Power BI, Metabase, Superset, ...) at the `marts` schema. For Fabric, deploy workspace items with fabric-cicd.

## DuckDB versions

dlt uses DuckDB 2 and SQLMesh DuckDB 1.5: every DuckDB file of the recipe is created with storage version v1.4.0, readable by both. Keep this when editing the package.
