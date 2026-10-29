# Acceptance and boundaries: Gitleaks

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain Redacted native findings, scanner identity and remediation guidance; retain original source privately.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Do not copy discovered secrets into chat or delivery archives. Redact both logs and reports. A match needs triage; remediation may require credential rotation, not only deleting a line.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
