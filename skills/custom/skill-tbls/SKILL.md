---
name: skill-tbls
description: "Data catalog and schema documentation. Generate the data catalog from the schema model: Markdown pages per table, ER diagram, relations, labels and description coverage."
---
# tbls

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model. Version selection belongs to the environment interface, not this skill.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools tbls` or `tbls-cli commands`. The adapter exposes bounded workflows, not the entire upstream API. For the end-to-end data pipeline (schema model, replica, catalog, stub data, ingestion, transformation, production package) follow skill-data-pipeline.

## Method

1. Identify the requested outcome, native source format, input provenance, dependencies and acceptance evidence before execution.
2. Choose tbls for this capability: Generate the data catalog from the schema model: Markdown pages per table, ER diagram, relations, labels and description coverage.
3. The catalog documents the model it is given; descriptions, owners and business meaning must be confirmed by people who know the data.
4. Work in the assignment's isolated staging directory; project inputs are read-only. Use a fresh absolute output directory. Inspect scripts and embedded resources before executing them.
5. Run a small representative test, inspect actual output, then extend only if the method meets the requested quality. Preserve parameters, dependency versions and unsuccessful checks.

## Delivery: editable sources and compatibility

Preserve: Schema model JSON, generated tbls schema, configuration, Markdown pages and ER diagram. Record products, sources and reports separately in `delivery.files` and `delivery.components`. Reopen the exact saved files and rerun the documented operation. State checks separately; never claim a check that did not run.

For learning, retain general, evidenced improvements rather than customer facts. Never retain secrets or private project data as reusable experience.

Upstream: https://github.com/k1LoW/tbls
