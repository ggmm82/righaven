# Acceptance and boundaries: OpenModelica

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain MO models, MOS recipe, parameters, local libraries, units and simulation data.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Do not silently download libraries. Use explicit initial conditions and solver settings, check actual simulation success and numerical plausibility. This is not engineering certification.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
