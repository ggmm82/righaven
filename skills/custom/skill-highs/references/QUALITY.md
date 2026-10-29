# Acceptance and boundaries: HiGHS

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain LP/MPS model, objective/constraints/units, solver settings, solution and native status.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Distinguish optimal, feasible, infeasible, unbounded and time-limited outcomes. Never present an infeasible model or a time-limited incumbent as a proven optimum.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
