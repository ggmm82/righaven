# Analytical quality: usql

Validate one SELECT, confirm the real driver and use read-only database credentials. Client driver availability does not prove a remote connection was tested.

Required evidence: source provenance, snapshot/time range, actual fields/types, declared keys, aggregation grain, row counts, null handling, units, time zones and reconciliation against a small known result. A plausible chart or successful SQL parse does not prove the user's analytical claim. Preserve source queries, models and tests, and label inferred associations as hypotheses.

Editable sources: SQL, bounded result JSON and local database snapshot or external-source requirements.

Use an independent review on the exact final report and dataset, not an earlier preview. Missing credentials, missing schema, unsupported driver or unavailable visual inspection must be explicit; do not silently replace the requested output.
