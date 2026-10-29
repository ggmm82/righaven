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
  permits local DuckDB projects only. `apply_local` must be explicit; there is
  no automatic production database deployment.
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
values. Database files produced by different DuckDB versions can be incompatible;
use the portable JSONL snapshot between tool environments.

The repository's real native fixtures create customers and orders with a declared
foreign key and a known total of 60. They exercise JDBC schema export, native SQL
queries, dlt extraction, SQL lineage and a tested local SQLMesh transformation.
The existing reporting fixtures check notebooks/HTML/PDF separately. Those
fixtures do not certify every external database, its network access or the
business meaning of an arbitrary dataset.
