# Phases and gates

Every call writes a fresh `output` folder with `receipt.json` and the sources it used. A gate passes only on the evidence listed; otherwise stop, report the gap and ask.

| # | Operation(s) | Gate evidence |
|---|---|---|
| 1 | read documents (pdf/docx/xlsx tools as needed) | inventory: source engine and dialect, warehouse target, BI tool, schedule, environments, open questions |
| 2 | `sqlglot.model` (`input` DDL + `dialect`, or `dlt.discover` result, or `duckdb.infer` model; `overrides` = documentation YAML/JSON) | `result.json` summary: tables, foreign keys, description coverage, PII count; `issues.md` reviewed |
| 3 | `tbls.document`, `tbls.lint` | `catalogo/README.md` + ER diagram; lint `findings.txt` empty or accepted by the user |
| 4 | `sqlglot.ddl` (`duckdb`, plus source/target), `duckdb.replicate` (`model` given) | `verification.json`: every table present with the expected columns and primary key; listed engine limits |
| 5 | `faker.generate` batch 0 on `replica.duckdb`; next batches with `database` = previous `stub.duckdb` | manifest per batch; zero orphan rows on each foreign key (DuckDB enforces them); same seed and batch reproduce identical files |
| 6 | `sqlglot.scaffold` (`dialect` = warehouse: postgres, tsql, fabric or duckdb; cron arguments) | package file list; `ingestion/tables.json` keys and cursors confirmed with the user; marts written from agreed definitions |
| 7 | `dlt.run` (`input` = `package/ingestion/pipeline.py`, `resource_dir` = `package/ingestion`, `source_database` = stub), `sqlmesh.plan` (`input` = `package/transform/config.yaml`, `resource_dir` = `package/transform`, `warehouse` = run output `warehouse.duckdb`, `apply_local: true`) | loaded row counts per table; plan applied with audits; one mart total reconciled with the stub source |
| 8 | `supercronic.validate`, `hadolint.lint`, `shellcheck.lint`, `actionlint.lint`, `gitleaks.scan` | valid crontab with no secrets; linters clean or findings justified; no secrets found |

## Periodic generation and scheduled runs

- Stub batches are numbered; dates move one day per batch from 2026-01-01 and keys never overlap, so batch N can reference parents of earlier batches. In the package the `stubs` job runs `stubgen.py --batch auto` against the test replica; it is disabled when `PIPELINE_ENV=prod`.
- Ingestion uses dlt `merge` on tables with a primary key and `append` otherwise; incremental cursors are only NOT NULL modified/created timestamps. Confirm them: a wrong cursor silently skips changes.
- SQLMesh `run` processes the intervals due according to each model's `cron`; `deploy` (`plan --auto-apply`) applies model changes and is a release step.

## File sources (XML, JSON, Parquet, CSV)

Use `duckdb.infer` on a representative folder. XML records (repeated children of the root, or `record`) become JSON Lines with attributes as `@name`; nested elements are kept as JSON text. Inferred keys and relations are candidates: confirm them in the documentation before the model is used for stub data.

## Oracle or documentation only

Write the DDL from the documentation in Oracle (or the documented) dialect, or write the model directly in YAML (see MODEL.md), then continue from phase 2. Mark the source as documented: it was not read from a database.
