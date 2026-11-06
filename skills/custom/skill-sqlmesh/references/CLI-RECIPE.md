# Native workflow: SQLMesh

Use `sqlmesh-cli commands` for authoritative JSON schemas. Operations: sqlmesh.plan.

- Input/output paths must be absolute and scoped to the job; output must be new.
- Local fixtures use a small SQLite database with customers/orders, three orders and a known total of 60.
- A private connection file uses a SQLAlchemy/MongoDB `url`; SchemaCrawler can instead use a plain `jdbc_url` and separate `username`/`password`. Keep this file outside Sources and resource_dir. Use authorized=true only for an authorized external source.
- Use `database` for a local SQLite source. `sqlglot.analyze` takes SQL and optional actual schema; `sqlmesh.plan` takes config.yaml plus a complete local project resource_dir.
- Read receipt.json and native logs, reconcile known values and preserve limits. Sources include editable recipes; credentials are never part of the archive.
- The executable minimum fixture is `scripts/acceptance_data.py`, case `sqlmesh`. Run it in the selected native environment; registration alone is not evidence.

Explain the actual graph and reconcile known totals. Apply only when apply_local=true, in the isolated copied project. This adapter does not deploy to remote production. Exchange JSONL/CSV/Parquet rather than assuming all DuckDB file versions interoperate.

The delivery must include editable inputs, outputs and a reproducible opening/regeneration guide, without credentials.
