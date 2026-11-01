# Native recipe: supercronic

Discover the exact schema with `supercronic-cli commands`. Supported operations: `supercronic.validate`.

1. Prepare the schema model or native input; read executable content before running it.
2. Invoke `supercronic-cli call OPERATION 'JSON_ARGUMENTS'` with absolute paths and a fresh absolute `output` directory inside `$RIGHAVEN_OUTPUT_DIR`.
3. Inspect native logs and `receipt.json`, not only the exit code. Keep reports and sources separate from the user-facing product.
4. Reopen the actual result and compare it with a known expected value or deliberately invalid fixture.
5. Populate `delivery.files`, `delivery.components`, checks and limitations with the observed evidence.

The executable minimum fixture is `scripts/acceptance_pipeline.py`, case `supercronic`. Environment preparation runs that real native fixture before marking programs ready. Registration alone is not execution evidence.

Validation checks crontab syntax only; job duration, overlaps and time zone must be tested in the target environment.
