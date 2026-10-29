# Native workflow: SQLGlot

Use `sqlglot-cli commands` for authoritative JSON schemas. Operations: sqlglot.analyze.

- Input/output paths must be absolute and scoped to the job; output must be new.
- Local fixtures use a small SQLite database with customers/orders, three orders and a known total of 60.
- A private connection file uses a SQLAlchemy/MongoDB `url`; SchemaCrawler can instead use a plain `jdbc_url` and separate `username`/`password`. Keep this file outside Sources and resource_dir. Use authorized=true only for an authorized external source.
- Use `database` for a local SQLite source. `sqlglot.analyze` takes SQL and optional actual schema; `sqlmesh.plan` takes config.yaml plus a complete local project resource_dir.
- Read receipt.json and native logs, reconcile known values and preserve limits. Sources include editable recipes; credentials are never part of the archive.
- The executable minimum fixture is `scripts/acceptance_data.py`, case `sqlglot`. Run it in the selected native environment; registration alone is not evidence.

Parsing does not execute SQL or prove database semantics. Unknown columns, wildcard expansion, dynamic SQL and missing schema remain explicit limits; never invent lineage. Use SchemaCrawler/dlt for live metadata and SQLMesh for executable model plans.

The delivery must include editable inputs, outputs and a reproducible opening/regeneration guide, without credentials.
