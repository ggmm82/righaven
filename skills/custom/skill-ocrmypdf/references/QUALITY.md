# Acceptance and boundaries: OCRmyPDF

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain Original scan, searchable PDF, sidecar, language and OCR recipe.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Do not replace original scans. Check names, numbers, reading order and language against sampled images; OCR confidence is not accuracy. This adapter does not claim PDF/A.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
