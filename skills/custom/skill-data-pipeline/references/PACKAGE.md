# Exported data project (`sqlglot.scaffold`)

The coordinator and specialists prepare these artifacts. Do not ask the user to write technical configuration or complete bracketed prompts.

```
package/
  package-spec.json               managed template identity for project-specific verification
  README.md                       deployment and operating guide
  schema/                         documented model and empty-replica DDL
  ingestion/pipeline.py           dlt acquisition; unconfirmed cursors use repeatable snapshots
  ingestion/tables.json           keys, proposed cursors and explicit confirmation flags
  ingestion/requirements.lock     included hashes, not a task left to the user
  transform/config.yaml           local data-volume gateway and production configuration
  transform/models/               staging and agreed business marts
  transform/requirements.lock     separately locked SQLMesh environment
  stubs/stubgen.py                 deterministic synthetic batches
  reporting/metrics.json          editable business SQL; replace generated example counts
  ops/orchestrate.py               ordered, locked cycles and durable state
  ops/schedules.json              independent stub, ingestion and transformation frequencies
  ops/crontab                     minute ticks; only due work runs
  ops/entrypoint.sh               schedule, init, cycle, report, health or explicit command
  compose.yaml                    portable non-root runtime and optional local report server
  compose.lab.yaml                actual PostgreSQL synthetic source, for PostgreSQL projects
  .env.example                    defaults and external connection placeholders, no secrets
```

## Required before delivery

1. Agree the actual business measures, grain and reconciliation rules; replace example marts and report queries.
2. Use `harness_package_check` on the actual package directory, not on an example from another project. This builds the exact managed Dockerfile and executes synthetic cycles and restart under the shared resource budget. Correct failures before submitting the package phase.
3. Retain its host-owned `package-check.json`, command log and actual HTML/query results. The guided package gate rejects invented success reports and changed package contents.
4. For PostgreSQL source projects, the additional lab Compose creates the source engine from the documented schema on a private, portless network and seeds it with synthetic snapshots. State whether that native path was actually tested. Other source engines remain simulations until a compatible native replica is provisioned and verified.
5. Deliver the approved report and its editable sources. The local HTML renderer works offline; native Power BI/Metabase/Superset formats require real adapters and checks when selected. BI-ready tables alone do not satisfy report delivery.

## Deployment responsibilities

The synthetic package needs no real database account. Its volume retains SQLMesh state, acquisition state, synthetic data and reports across container replacement. Build and startup commands must work exactly as documented. Include environment-specific production configuration and secret references without secret values. Only production activation, real credentials and checks on external systems may remain explicitly unperformed; do not leave dependency locking, basic package assembly or local smoke testing to the user.

`PIPELINE_ENV=prod` disables synthetic generation. Incremental loading must be explicitly confirmed after key, update/delete and replay tests. Native Fabric and source-engine-specific behavior need target verification; generating configuration is not deployment evidence.

## DuckDB compatibility

The ingestion and transformation environments may use different DuckDB releases. Every shared database uses storage version v1.4.0; retain this when editing the package. Worker software environments are reusable tools; project data and service lifetime remain separate.
