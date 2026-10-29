# Acceptance and boundaries: PrusaSlicer

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain Original mesh or 3MF project, printer/material INI, slicing recipe and G-code.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Do not replace CAD/mesh authoring tools. G-code is machine-specific; confirm printer, bed, nozzle, temperatures, supports and scale before use. Do not claim a physical print was tested.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
