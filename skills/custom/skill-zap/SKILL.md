---
name: skill-zap
description: "Passive application security checks. Spider an authorized application and collect passive security findings with an explicit automation plan."
---
# OWASP ZAP

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model. Version selection belongs to the environment interface, not this skill.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools zap` or `zap-cli commands`. The adapter exposes bounded workflows, not the entire upstream API.

## Method

1. Identify the requested outcome, native source format, input provenance, dependencies and acceptance evidence before execution.
2. Choose OWASP ZAP for this capability: Spider an authorized application and collect passive security findings with an explicit automation plan.
3. The adapter contains no activeScan job. Spidering still sends requests and can affect poorly designed applications. Keep target scope narrow, triage findings and distinguish an incomplete scan from no findings.
4. Work in the assignment's isolated staging directory; project inputs are read-only. Use a fresh absolute output directory. Inspect scripts and embedded resources before executing them.
5. Run a small representative test, inspect actual output, then extend only if the method meets the requested quality. Preserve units, parameters, dependency versions and unsuccessful checks.

## Delivery: editable sources and compatibility

Preserve: Authorization/scope, automation plan, native XML report and reproduction guidance. Record products, sources and reports separately in `delivery.files` and `delivery.components`. A recipe or export does not replace a requested native project. Reopen the exact saved files, relocate the complete source package and rerun the documented operation. State native CLI, GUI and visual checks separately; never claim a check that did not run.

For learning, retain general, evidenced improvements rather than customer facts. Technical tool-operation lessons require a reproducible test; high-level production methods require the user's acceptance. Never retain secrets or private project data as reusable experience.

Upstream: https://github.com/zaproxy/zaproxy
