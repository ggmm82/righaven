# Native recipe: minimap2

Discover the exact schema with `minimap2-cli commands`. Supported operations: `minimap2.align`.

1. Prepare a valid local native input and required local resources; read executable content before running it.
2. Invoke `minimap2-cli call OPERATION 'JSON_ARGUMENTS'` with an absolute `input` where required and a fresh absolute `output` directory inside `$RIGHAVEN_OUTPUT_DIR`. Consult the schema for operation-specific required parameters; placeholders are not runnable inputs.
3. Inspect native stdout/stderr and `receipt.json`, not only the exit code. Keep reports and sources separate from the user-facing product.
4. Reopen the actual result and compare it with a known expected value or deliberately invalid fixture. Extract/move source packages and repeat to establish portability.
5. Populate `delivery.files`, `delivery.components`, checks and limitations with the observed evidence.

The executable minimum fixture is `scripts/acceptance_domain.py`, case `minimap2`. Environment preparation runs that real native fixture before marking programs ready. Registration alone is not execution evidence; a workflow that fails remains unprepared.

Mapping positions depend on preset and reference; alignment is evidence for interpretation, not a variant call.
