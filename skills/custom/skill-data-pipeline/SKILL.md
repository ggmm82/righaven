---
name: skill-data-pipeline
description: "Recipe: end-to-end data pipeline. From database documentation and schema analysis to a described catalog, an empty local replica, periodic stub data, scheduled ingestion, tested transformations, BI-ready marts and a production package (Docker + supercronic, PostgreSQL, SQL Server or Microsoft Fabric)."
metadata:
  righaven-tools: [sqlglot, duckdb, tbls, faker, dlt, sqlmesh, supercronic, hadolint, shellcheck, actionlint, gitleaks]
---
# Recipe: end-to-end data pipeline

A recipe is a tested sequence of catalog operations with a gate after each phase. It is not a fixed role: compose the team from the request, but keep the phases, the evidence and the order. Each tool skill (skill-sqlglot, skill-duckdb, skill-tbls, skill-faker, skill-dlt, skill-sqlmesh, skill-supercronic) gives exact arguments; discover them with `craft tools TOOL`.

Read [PHASES.md](references/PHASES.md) for every phase and gate, [MODEL.md](references/MODEL.md) for the schema model and the documentation overrides, and [PACKAGE.md](references/PACKAGE.md) for the delivered package and its release. [QUALITY.md](references/QUALITY.md) lists what a reviewer must find before acceptance.

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
- The package is a tested starting point: hashed lock files, base image digest, credentials and the first `deploy` belong to the user's release process and are listed as next steps.

## Delivery: editable sources and compatibility

Deliver: the catalog (Markdown + ER), `model.json` with the documentation file, DDL per dialect, the empty replica and stub databases only when useful as test fixtures, the production package folder, and a report with every gate's evidence. Record products, sources and reports separately in `delivery.files` and `delivery.components`. Never claim a check that did not run.
