# Acceptance and boundaries: QGIS Processing

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain QGIS projects when authored, input layers/styles, parameter JSON and output layers.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: A Processing output is not automatically a complete QGIS project. Check CRS, geometry, units and relative dependencies; do not rely on unavailable plugins or external providers.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
