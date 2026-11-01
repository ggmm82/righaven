# Acceptance and boundaries: supercronic

- Outcome: verify the requested content, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain crontab and native validation output.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks.
- Scope: Validation checks crontab syntax only; job duration, overlaps and time zone must be tested in the target environment.
- Delivery: distinguish primary product, editable source and report; document prerequisites missing outside RigHaven.
- Independent review: if a required check is unavailable, mark it `not_run` with a concrete next step.
