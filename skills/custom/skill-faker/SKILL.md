---
name: skill-faker
description: "Synthetic test data. Generate deterministic, foreign-key consistent stub data from the schema model for a batch (periodic runs use increasing batch numbers) into a DuckDB copy and Parquet/CSV/JSON Lines/XML files."
---
# Faker

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model. Version selection belongs to the environment interface, not this skill.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools faker` or `faker-cli commands`. The adapter exposes bounded workflows, not the entire upstream API. For the end-to-end data pipeline (schema model, replica, catalog, stub data, ingestion, transformation, production package) follow skill-data-pipeline.

## Method

1. Identify the requested outcome, native source format, input provenance, dependencies and acceptance evidence before execution.
2. Choose Faker for this capability: Generate deterministic, foreign-key consistent stub data from the schema model for a batch (periodic runs use increasing batch numbers) into a DuckDB copy and Parquet/CSV/JSON Lines/XML files.
3. Stub data is synthetic: value distributions and correlations do not reproduce production data; updates and deletions are not simulated.
4. Work in the assignment's isolated staging directory; project inputs are read-only. Use a fresh absolute output directory. Inspect scripts and embedded resources before executing them.
5. Run a small representative test, inspect actual output, then extend only if the method meets the requested quality. Preserve parameters, dependency versions and unsuccessful checks.

## Delivery: editable sources and compatibility

Preserve: Schema model, generator script, per-batch CSV/Parquet/JSON Lines/XML files, stub DuckDB database and manifest. Record products, sources and reports separately in `delivery.files` and `delivery.components`. Reopen the exact saved files and rerun the documented operation. State checks separately; never claim a check that did not run.

For learning, retain general, evidenced improvements rather than customer facts. Never retain secrets or private project data as reusable experience.

Upstream: https://github.com/joke2k/faker
