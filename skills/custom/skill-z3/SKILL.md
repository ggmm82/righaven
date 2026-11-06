---
name: skill-z3
description: "SMT solving and logical verification. Check an SMT-LIB 2 problem with the Z3 solver; report sat, unsat or unknown with the model or core it prints."
---
# Z3

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model. Version selection belongs to the environment interface, not this skill.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools z3` or `z3-cli commands`. The adapter exposes bounded workflows, not the entire upstream API.

## Method

1. Identify the requested outcome, native source format, input provenance, dependencies and acceptance evidence before execution.
2. Choose Z3 for this capability: Check an SMT-LIB 2 problem with the Z3 solver; report sat, unsat or unknown with the model or core it prints.
3. unknown or a timeout is not a proof; a model satisfies the encoded constraints only, not unstated requirements.
4. Work in the assignment's isolated staging directory; project inputs are read-only. Use a fresh absolute output directory. Inspect scripts and embedded resources before executing them.
5. Run a small representative test, inspect actual output, then extend only if the method meets the requested quality. Preserve units, parameters, dependency versions and unsuccessful checks.

## Delivery: editable sources and compatibility

Preserve: SMT-LIB problem, solver answer and model. Record products, sources and reports separately in `delivery.files` and `delivery.components`. A recipe or export does not replace a requested native project. Reopen the exact saved files, relocate the complete source package and rerun the documented operation. State native CLI, GUI and visual checks separately; never claim a check that did not run.

For learning, retain general, evidenced improvements rather than customer facts. Technical tool-operation lessons require a reproducible test; high-level production methods require the user's acceptance. Never retain secrets or private project data as reusable experience.

Upstream: https://github.com/Z3Prover/z3
