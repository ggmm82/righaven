---
name: skill-data-pipeline
description: "Recipe: end-to-end data pipeline. From database documentation and schema analysis to a described catalog, an empty local replica, periodic stub data, scheduled ingestion, tested transformations, BI-ready marts and a production package (Docker + supercronic, PostgreSQL, SQL Server or Microsoft Fabric)."
metadata:
  righaven-tools: []
---
# Recipe: end-to-end data pipeline

This is a guided project method, not a program or fixed specialist. Read the persisted journey using harness_journey. Compose dynamic roles and choose only the authorized capabilities needed for the current result; reading this method does not install every program. The journey stores owner answers, activity bindings, hashed evidence and owner-only approval gates. Start a phase with native step IDs; submit actual evidence when ready. Never approve your own phase. Each tool skill (skill-sqlglot, skill-duckdb, skill-tbls, skill-faker, skill-dlt, skill-sqlmesh, skill-supercronic) gives exact arguments; discover them with `craft tools TOOL`.

Read [PHASES.md](references/PHASES.md) for every phase and gate, [MODEL.md](references/MODEL.md) for the schema model and the documentation overrides, and [PACKAGE.md](references/PACKAGE.md) for the delivered package and its release. [QUALITY.md](references/QUALITY.md) lists what a reviewer must find before acceptance. Starting this guided project automatically pins its release policy beside organization policies. Other project types are unaffected. [policy-sheet.json](references/policy-sheet.json) documents the baseline; the journey pins the selected version, including real BI and exported-package checks.

## When to use it

The user has documentation or an analysis of a database (DDL, a dictionary, PDFs, spreadsheets, files in JSON/XML/Parquet/CSV, or an authorized read-only connection) and needs some or all of: a described catalog, a local empty replica, periodic synthetic test data, scheduled acquisition, periodic transformation, marts for the existing BI tool and a package to take to production. Start from the phases the user asked for; do not add phases they excluded.

## Phases (each ends with a checkpoint with the user when the result changes later work)

1. **Sources and scope**: inventory the documents, the source engine and dialect, the production warehouse, the BI tool, schedule and environments. Record unknowns as questions, not assumptions.
2. **Schema model**: `sqlglot.model` from DDL in the source dialect, from `dlt.discover` on an authorized read-only connection, or from `duckdb.infer` on sample files. Apply the documentation with `overrides` (descriptions, owners, PII, documented relations, row volumes, stub hints). Observed and documented structure stay distinct.
3. **Catalog**: `tbls.document` (Markdown pages, ER diagram, coverage) and `tbls.lint`. Close the gaps with the user; a catalog with undescribed tables or columns is a draft.
4. **Empty local replica**: `sqlglot.ddl` (dialect duckdb, plus the source/target dialects for review) and `duckdb.replicate` with the model for verification.
5. **Periodic stub data**: `faker.generate` on the replica, batch 0, then further batches on the previous stub database. Check orphans, constraints and reproducibility.
6. **Production package**: `sqlglot.scaffold` with the production warehouse dialect and the agreed schedule. Edit the marts with the user's business definitions; keep staging generated from the model.
7. **Local end-to-end test**: `dlt.run` of `ingestion/pipeline.py` on the stub database, then `sqlmesh.plan` of `transform/` with `warehouse` set to the loaded DuckDB and `apply_local: true`. Reconcile at least one mart total with the source.
8. **Release checks**: `supercronic.validate` on `ops/crontab`, `hadolint.lint` on the Dockerfile, `shellcheck.lint` on `ops/*.sh`, `actionlint.lint` on the CI workflow, `gitleaks.scan` on the package. Deliver the package with the evidence and the list of checks not performed (real source, real warehouse, volumes, BI).

## Rules

- Never connect to production systems from RigHaven unless the user authorizes a read-only account for discovery; credentials stay in private connection files or environment variables, never in models, packages, logs or lessons.
- Personal data columns are always synthetic in stub data; mark them `pii: true` in the model.
- State what each engine cannot enforce (for example Fabric Warehouse keys) and keep those checks as SQLMesh audits.
- The package is a tested starting point: hashed lock files are included. Build and start the exact exported package and verify a second run and restart. Actual production activation still requires target authorization and credentials; distinguish locally verified package from production verification.

## Delivery: editable sources and compatibility

Deliver: the catalog (Markdown + ER), `model.json` with the documentation file, DDL per dialect, the empty replica and stub databases only when useful as test fixtures, the production package folder, and a report with every gate's evidence. Record products, sources and reports separately in `delivery.files` and `delivery.components`. Never claim a check that did not run.

## User journey and runtime contracts

Read attachments first; infer schema and catalog entries with provenance. Ask at most three consequential unanswered questions with a recommendation. Never ask the user to author SQL, JSON, YAML, cursor mappings or CLI commands. Connections are optional; a documents-only project must progress with synthetic local data.

Keep the full requested outcome: catalog, empty replica, evolving synthetic scenarios, scheduled ingestion, scheduled transformations, actual business reports with editable sources and an exported deployable package. BI-ready tables or example row counts do not satisfy business reporting. Agree dimensions, measures, grain and reconciliation rules with the owner and replace reporting/metrics.json examples. An interactive portable HTML report is available for the local path; Power BI/Metabase/Superset require their real adapters and native sources when chosen.

DuckDB is an explicitly labelled simulation, not proof of compatibility with the source database. For a faithful replica provision and verify the selected source engine, or ask the owner to approve simulation for the laboratory. Preserve the original dialect and document unsupported constructs. Do not mark source-engine compatibility passed solely from SQL re-parsing.

The exported runtime keeps SQLMesh state, pipeline state and outputs under DATA_DIR. Temporary RigHaven workers are builders, not the lifetime of the delivered laboratory. Native project services must be managed or deployed explicitly; do not hide servers inside a worker.

Default loads are repeatable full snapshots. Incremental cursors are proposals: enable only after confirming update/delete semantics, keys, late arrivals and replay tests. Test duplicate prevention and recovery, not only an initial load. The cycle orders stub generation, ingestion and transformations under one shared-storage lock.

Use role connections only when needed: reference the owner-authorized IDs in the role's connections field. Never give a document reviewer database credentials. Reuse centralized model-provider authentication; do not add a second CLI login inside a data environment.
