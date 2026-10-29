# Analytical quality: SQLGlot

Parsing does not execute SQL or prove database semantics. Unknown columns, wildcard expansion, dynamic SQL and missing schema remain explicit limits; never invent lineage. Use SchemaCrawler/dlt for live metadata and SQLMesh for executable model plans.

Required evidence: source provenance, snapshot/time range, actual fields/types, declared keys, aggregation grain, row counts, null handling, units, time zones and reconciliation against a small known result. A plausible chart or successful SQL parse does not prove the user's analytical claim. Preserve source queries, models and tests, and label inferred associations as hypotheses.

Editable sources: Original SQL, actual schema dictionary, normalized SQL, lineage JSON and limits.

Use an independent review on the exact final report and dataset, not an earlier preview. Missing credentials, missing schema, unsupported driver or unavailable visual inspection must be explicit; do not silently replace the requested output.
