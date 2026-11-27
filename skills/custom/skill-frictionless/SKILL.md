---
name: skill-frictionless
description: "Build and verify portable data contracts for local tabular deliveries with Frictionless."
---

# Frictionless

Use this tool when a dataset delivery needs an explicit contract for fields, types, keys and constraints. Use DuckDB for exploratory SQL and SQLMesh for transformation tests. Use Frictionless to check the files the recipient will actually receive.

Inspect the local source and preserve it. Start with the user's declared schema when available. Treat inferred fields as a draft and confirm dates, encodings, null conventions, identifier types, keys and foreign relationships before accepting it. Validate candidate outputs without changing the constraints to conceal failures. Inspect and resolve every issue reported in the JSON.

## Delivery: editable sources and compatibility

Deliver the original or requested transformed datasets with the editable `datapackage.json` and JSON validation report. Use paths relative to the package directory and include every referenced resource. Validate the copied delivery. Document any corrections and checks that need a different tool, such as business reconciliation or scheduling.

See [the CLI recipe](references/CLI-RECIPE.md), [capabilities](references/CAPABILITIES.md) and [quality checks](references/QUALITY.md).
