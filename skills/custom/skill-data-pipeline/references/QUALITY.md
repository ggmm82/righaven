# Acceptance of the recipe

A reviewer accepts the delivery only when these are observable:

- **Model**: every table of the documentation is present, keys and relations are either declared or explicitly documented; `issues.md` items are resolved or accepted.
- **Catalog**: descriptions for every table and for the columns the user cares about; PII labelled; ER diagram readable.
- **Replica**: `verification.json` without mismatches; engine limits listed.
- **Stub data**: at least two batches, zero orphan rows, CHECK constraints respected, reproducible files.
- **Pipeline**: local `dlt.run` row counts equal the stub source; SQLMesh plan applied with audits; a mart total reconciled.
- **Package**: crontab valid, linters clean or justified, no secrets, runbook with release steps and the checks not performed.

Not covered by the recipe and never to be claimed: connectivity, permissions and performance on the real systems, correctness of business definitions not confirmed by the user, BI reports.
