# Native workflow: usql

Use `usql-cli commands` for authoritative JSON schemas. Operations: usql.query.

- Input/output paths must be absolute and scoped to the job; output must be new.
- Local fixtures use a small SQLite database with customers/orders, three orders and a known total of 60.
- A private connection file uses a SQLAlchemy/MongoDB `url`; SchemaCrawler can instead use a plain `jdbc_url` and separate `username`/`password`. Keep this file outside Sources and resource_dir. Use authorized=true only for an authorized external source.
- Use `database` for a local SQLite source. `sqlglot.analyze` takes SQL and optional actual schema; `sqlmesh.plan` takes config.yaml plus a complete local project resource_dir.
- Read receipt.json and native logs, reconcile known values and preserve limits. Sources include editable recipes; credentials are never part of the archive.
- The executable minimum fixture is `scripts/acceptance_data.py`, case `usql`. Run it in the selected native environment; registration alone is not evidence.

Validate one SELECT, confirm the real driver and use read-only database credentials. Client driver availability does not prove a remote connection was tested.

The delivery must include editable inputs, outputs and a reproducible opening/regeneration guide, without credentials.
