# Data Engineering in RigHaven

The preset combines existing notebook/report capabilities with five complementary
open-source data tools. It is a toolbox for dynamic roles, not a fixed workflow or
an extra mandatory team. A coordinator can use it alongside other environments,
including independent assignments in parallel, within the resource budget.

## Start with a bounded question

Specify authorized source systems, tables or collections, analytical question,
time range, aggregation grain, audience and delivery format. Start with a small
known-result query. Distinguish declared metadata from sampled structure,
inferred relationships and business hypotheses. Check join cardinalities,
nulls, units, time zones, duplicates and reconciliation before expanding work.

Use `craft capabilities TOOL`, `craft commands TOOL` and `craft tools TOOL` for
the installed adapter contract. Adapters operate on copies in assignment staging;
existing project input is read-only. Native CLIs remain available for additional
operations, subject to the same user authorization and capability policy.

## Connections

For a supplied local SQLite database, use the adapter's `database` path: a copy
is retained in the delivery sources and the original is unchanged. Treat such a
snapshot as private project data, not as a public Gallery asset.

For a remote database, explicitly authorize the source and use a database account
with read-only permissions. Supply a private scoped `connection_file` outside
any source `resource_dir`, for example:

```json
{"url": "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"}
```

For SchemaCrawler, an explicit JDBC URL with separate credentials is also accepted:

```json
{"jdbc_url": "jdbc:postgresql://HOST:5432/DATABASE", "username": "USER", "password": "PASSWORD"}
```

These are placeholders, not working credentials. Do not paste real values into
chat prompts, skill instructions, notebooks, SQL, logs or Gallery metadata. The
adapter keeps connection configuration in a private temporary file, redacts
native logs and excludes it from receipts and sources. It does not create a
connection-vault UI. `connection_env` is available only when a matching
`RIGHAVEN_DB_*` secret has actually been supplied to that job; it is not
automatically forwarded from the Gateway.

The SELECT validator prevents ordinary DDL/DML in adapter queries; read-only
server permissions are still required. SchemaCrawler reads JDBC metadata rather
than running project transformation scripts. MongoDB discovery samples only five
documents per collection and reports this limit. The extracted row cap is
100,000; this is not a complete backup or a consistent cross-system snapshot.

### User connections

Users register SQL Server, PostgreSQL, MySQL/MariaDB and Microsoft Entra ID connections on the
**Connections** page and assign them to a task from its project panel. Details: [Connections](CONNECTIONS.md).
A role declares `connections: ["ID"]` and the adapters receive `connection: "ID"`.

## Tool choices and upstream references

- [usql](https://github.com/xo/usql), MIT: one native SQL shell across database
  drivers, retaining the actual query and JSON results.
- [SchemaCrawler](https://www.schemacrawler.com/), bundled JDBC distribution
  [GPL v3](https://www.schemacrawler.com/license.html): reverse engineering from
  actual metadata and declared constraints. JDBC drivers retain their notices.
  [JSON serialization](https://www.schemacrawler.com/serialize.html) uses the
  native serialized catalog, not a fabricated database model.
- [dlt](https://dlthub.com/docs/reference/command-line-interface), Apache 2.0:
  schema discovery and extraction, using SQLAlchemy and MongoDB drivers, with a
  private local DuckDB destination and editable pipeline source.
- [SQLMesh](https://sqlmesh.readthedocs.io/en/latest/quickstart/cli/), Apache 2.0:
  SQL/Python projects, models, tests and development plans. The curated adapter
  executes only a local DuckDB gateway; production gateways may be declared in
  the same project with credentials from `env_var()` and are never contacted.
  `apply_local` must be explicit; there is no automatic production deployment.
- [SQLGlot](https://github.com/tobymao/sqlglot), MIT: parsing, dialect handling
  and table/column lineage. Supply real schema to establish column lineage.
- [Jupyter](https://jupyter.org/), [DuckDB](https://duckdb.org/),
  [Quarto](https://quarto.org/docs/interactive/) and [Typst](https://typst.app/):
  existing notebook, analysis, interactive HTML and paginated publication tools.
  Another overlapping reporting framework is not installed by default.

## Delivery and reproducibility

Keep the primary report, editable notebook/SQL/project, machine-readable data and
verification evidence separate. Include an opening/regeneration guide, tool
versions, observed source schema, snapshot limits and totals used for reconciliation.
Retain only authorized source data. Keep connection requirements without secret
values. Database files produced by different DuckDB versions can be incompatible:
the recipe creates every DuckDB file with storage version `v1.4.0`, readable by
the DuckDB 2 (dlt) and DuckDB 1.5 (SQLMesh, Faker) environments; otherwise use the
portable JSONL snapshot between tool environments.

The repository's real native fixtures create customers and orders with a declared
foreign key and a known total of 60. They exercise JDBC schema export, native SQL
queries, dlt extraction, SQL lineage and a tested local SQLMesh transformation.
The existing reporting fixtures check notebooks/HTML/PDF separately. Those
fixtures do not certify every external database, its network access or the
business meaning of an arbitrary dataset.

## Recipe: end-to-end data pipeline

Preset **Pipeline dati end-to-end** (`pipeline-dati`) with the recipe skill
`skill-data-pipeline`. It turns database documentation or a schema analysis into
a production package in eight phases, each closed by observable evidence:

| Phase | Operation | Evidence |
|---|---|---|
| Schema model | `sqlglot.model` from DDL in any dialect, `dlt.discover` on a read-only connection or `duckdb.infer` on JSON/XML/Parquet/CSV files, plus documentation `overrides` | engine-neutral `model.json`, description coverage, personal data columns, issues |
| Catalog | `tbls.document`, `tbls.lint` | Markdown pages per table, ER diagram, relations (documented ones shown as virtual), lint findings |
| Empty local replica | `sqlglot.ddl` (DuckDB, PostgreSQL, SQL Server, Fabric, MySQL, Oracle, SQLite), `duckdb.replicate` | re-parsed DDL, replica verified table by table against the model, engine limits |
| Periodic stub data | `faker.generate` | deterministic batches; keys never overlap; children reference parents of the same or earlier batches; foreign keys enforced by DuckDB; CSV/Parquet/JSON Lines/XML |
| Production package | `sqlglot.scaffold` | dlt ingestion with merge keys and incremental cursors, SQLMesh staging views with audits and an example mart, local and production gateways, stub job, supercronic crontab, locked job runner, Dockerfile, compose, CI and runbook |
| Local end-to-end test | `dlt.run`, `sqlmesh.plan` with `warehouse` | rows loaded per table, plan applied with audits, a mart total reconciled with the stub source |
| Release checks | `supercronic.validate`, `hadolint`, `shellcheck`, `actionlint`, `gitleaks` | valid schedule without secrets, linted container, scripts and CI, no secrets in the package |

The production package runs anywhere Docker runs: supercronic schedules
acquisition, transformation and (in test environments only) stub generation;
`ops/run.sh` locks each job so a slow run is skipped, never overlapped. The
warehouse can be PostgreSQL, SQL Server or a Microsoft Fabric Warehouse (dlt
`fabric` destination, SQLMesh `fabric` gateway, ODBC Driver 18); Fabric workspace
items such as semantic models and Power BI reports are deployed separately with
Microsoft's `fabric-cicd`. The existing BI tool reads the `marts` schema.

Tools added for the recipe: [tbls](https://github.com/k1LoW/tbls) (MIT),
[Faker](https://github.com/joke2k/faker) (MIT) and
[supercronic](https://github.com/aptible/supercronic) (MIT). tbls and supercronic
do not publish checksum files: the recorded SHA-256 was computed from the official
release downloads. The dlt environment also gains the `oracledb` driver for Oracle
discovery.

An administrator can publish `skills/custom/skill-data-pipeline/references/policy-sheet.json`
as an optional Policy Book sheet so the final validation checks the catalog, the reconciled mart,
the schedule and the absence of secrets (`no_secrets` probe). It is not installed by default,
because every optional sheet requires a coordinator decision in every project.

Not covered, and listed in every delivery: connectivity, permissions, volumes and
timings on the real source and warehouse, hashed production lock files and the base
image digest, business definitions of marts not confirmed by the user, BI reports.
No package has been executed against a Fabric tenant by RigHaven.
