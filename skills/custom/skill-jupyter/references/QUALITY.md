# Acceptance and boundaries: Jupyter

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain Input and executed IPYNB, datasets, environment requirements and figures.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Execute in a fresh kernel, in order. Clear stale outputs; preserve random seeds, dependencies and data provenance. Notebook execution is code execution, not a web notebook service.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
