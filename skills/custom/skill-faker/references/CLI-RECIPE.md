# Native recipe: Faker

Discover the exact schema with `faker-cli commands`. Supported operations: `faker.generate`.

1. Prepare the schema model or native input; read executable content before running it.
2. Invoke `faker-cli call OPERATION 'JSON_ARGUMENTS'` with absolute paths and a fresh absolute `output` directory inside `$RIGHAVEN_OUTPUT_DIR`.
3. Inspect native logs and `receipt.json`, not only the exit code. Keep reports and sources separate from the user-facing product.
4. Reopen the actual result and compare it with a known expected value or deliberately invalid fixture.
5. Populate `delivery.files`, `delivery.components`, checks and limitations with the observed evidence.

The executable minimum fixture is `scripts/acceptance_pipeline.py`, case `faker`. Environment preparation runs that real native fixture before marking programs ready. Registration alone is not execution evidence.

Stub data is synthetic: value distributions and correlations do not reproduce production data; updates and deletions are not simulated.
