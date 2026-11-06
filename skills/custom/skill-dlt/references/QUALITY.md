# Analytical quality: dlt

Separate SQL metadata, sampled document fields and business hypotheses. Keep pipeline state private per job, preserve type/null semantics and reconcile counts. External reads require authorized read-only credentials; no source-system writes are performed.

Required evidence: source provenance, snapshot/time range, actual fields/types, declared keys, aggregation grain, row counts, null handling, units, time zones and reconciliation against a small known result. A plausible chart or successful SQL parse does not prove the user's analytical claim. Preserve source queries, models and tests, and label inferred associations as hypotheses.

Editable sources: Python pipeline, schema YAML/JSON, query/inputs, portable JSONL, DuckDB snapshot and row reconciliation.

Use an independent review on the exact final report and dataset, not an earlier preview. Missing credentials, missing schema, unsupported driver or unavailable visual inspection must be explicit; do not silently replace the requested output.
