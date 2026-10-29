---
name: skill-schemacrawler
description: "Database reverse engineering. Inspect schema, declared keys, constraints, metadata, lint and relationship diagrams with real JDBC metadata."
---

# SchemaCrawler

This capability strengthens a dynamically assigned project role; it does not require a fixed specialist. Inherit the selected team model. Versions are managed in Environments, not in these instructions.

## When to use

Reverse engineer real keys, constraints, table relationships and schema metadata through JDBC.

Read [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md) and [QUALITY.md](references/QUALITY.md), plus skill-workspace's relevant execution/delivery protocol.

## Procedure

1. Establish the user's analytical question, source systems, authorization, snapshot/time range, intended audience and required outputs before work.
2. Discover exact arguments with `craft capabilities schemacrawler`, `craft commands schemacrawler` and `craft tools schemacrawler`. Use actual metadata, not imagined tables, CLI flags or API fields.
3. Separate declared constraints from inferred associations and sampled data. Validate business meaning with the owner; do not invent tables or relationships from names. The bundled distribution uses GPL v3 and retains JDBC notices.
4. Work only in this assignment's isolated staging folder. Treat project inputs as read-only, use a fresh absolute output directory and run a representative known-result check.
5. Record observed failures, missing checks and reconciliation; expand the method only after the representative result matches the user's goal.

## Credentials and privacy

Use an authorized read-only connection. Prefer a supplied `RIGHAVEN_DB_*` environment secret or a private connection JSON file outside deliverable resources. Never paste credentials into prompts, SQL, notebooks, published environment instructions, logs, catalog metadata or source archives. Preserve external connection requirements without their secret values.

## Delivery: editable sources and compatibility

Retain Schema JSON/HTML/DOT, database snapshot or connection requirements, diagrams and interpretation notes. Keep primary report, editable source, machine-readable data and technical evidence separate. Provide a short guide for opening, updating and regenerating the actual delivery. Interactive reports and paginated publications use the existing Quarto/Jupyter/Typst capabilities; do not install another overlapping reporting stack without a demonstrated need.

A passing command is not analytical correctness. Validate join cardinalities, units, nulls, time zones, aggregation grain and the intended business meaning. Save a transferable lesson only with evidence; methods still require user acceptance.

Upstream: https://github.com/schemacrawler/SchemaCrawler
