---
name: skill-usql
description: "Universal database SQL client. Read authorized databases through one native SQL shell; discover available drivers, retain queries and verify explicitly authorized destination loads."
---

# usql

This capability strengthens a dynamically assigned project role; it does not require a fixed specialist. Inherit the selected team model. Versions are managed in Environments, not in these instructions.

## When to use

Use one SQL client across supported relational database drivers for explicit read-only queries.

Read [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md) and [QUALITY.md](references/QUALITY.md), plus skill-workspace's relevant execution/delivery protocol.

## Procedure

1. Establish the user's analytical question, source systems, authorization, snapshot/time range, intended audience and required outputs before work.
2. Discover exact arguments with `craft capabilities usql`, `craft commands usql` and `craft tools usql`. Use actual metadata, not imagined tables, CLI flags or API fields.
3. Validate one SELECT and confirm the real driver for source reads. For an owner-authorized destination, execute the guarded load and read back the actual remote objects. Keep its connection-verification.json and reference it in handoff.connection_receipts. A local file or a successful connection probe does not prove the destination was populated. Report an access/driver/network failure and stop claiming completion; only the owner may defer a selected destination.
4. Work only in this assignment's isolated staging folder. Treat project inputs as read-only, use a fresh absolute output directory and run a representative known-result check.
5. Record observed failures, missing checks and reconciliation; expand the method only after the representative result matches the user's goal.

## Credentials and privacy

Use read-only credentials for source queries. A destination explicitly selected by the owner is a required outcome when task writing is authorized; do not replace it with a local database. For writes, assign both dlt and usql where needed (Microsoft/Fabric connections use the native usql driver) and use the guarded `dlt.load` operation, limited to the owner-enabled schema and explicit table list; do not invent arbitrary SQL write operations. Prefer a supplied `RIGHAVEN_DB_*` environment secret or a private connection JSON file outside deliverable resources. Never paste credentials into prompts, SQL, notebooks, published environment instructions, logs, catalog metadata or source archives. Preserve external connection requirements without their secret values.

## Delivery: editable sources and compatibility

Retain SQL, bounded result JSON and local database snapshot or external-source requirements. Keep primary report, editable source, machine-readable data and technical evidence separate. Provide a short guide for opening, updating and regenerating the actual delivery. Interactive reports and paginated publications use the existing Quarto/Jupyter/Typst capabilities; do not install another overlapping reporting stack without a demonstrated need.

A passing command is not analytical correctness. Validate join cardinalities, units, nulls, time zones, aggregation grain and the intended business meaning. Save a transferable lesson only with evidence; methods still require user acceptance.

Upstream: https://github.com/xo/usql
