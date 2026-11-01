# Acceptance and boundaries: Faker

- Outcome: verify the requested content, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain schema model, generator script, per-batch CSV/Parquet/JSON Lines/XML files, stub DuckDB database and manifest.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks.
- Scope: Stub data is synthetic: value distributions and correlations do not reproduce production data; updates and deletions are not simulated.
- Delivery: distinguish primary product, editable source and report; document prerequisites missing outside RigHaven.
- Independent review: if a required check is unavailable, mark it `not_run` with a concrete next step.
