# Acceptance and boundaries: KiCad

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain KICAD_PRO, KICAD_SCH, KICAD_PCB and any custom symbol/footprint libraries, plus fabrication exports when requested.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: SVG is an export, not an editable circuit source. Check ERC/DRC and footprints with native tools for manufacturing work; SVG export alone proves neither electrical correctness nor fabrication readiness.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
