---
name: skill-pari
description: "Number theory and exact arithmetic. Run a PARI/GP script (number theory, exact arithmetic, polynomials) and save its output."
---
# PARI/GP

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model. Version selection belongs to the environment interface, not this skill.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools pari` or `pari-cli commands`. The adapter exposes bounded workflows, not the entire upstream API.

## Method

1. Identify the requested outcome, native source format, input provenance, dependencies and acceptance evidence before execution.
2. Choose PARI/GP for this capability: Run a PARI/GP script (number theory, exact arithmetic, polynomials) and save its output.
3. Some functions are probabilistic (e.g. ispseudoprime); state which results are proven.
4. Work in the assignment's isolated staging directory; project inputs are read-only. Use a fresh absolute output directory. Inspect scripts and embedded resources before executing them.
5. Run a small representative test, inspect actual output, then extend only if the method meets the requested quality. Preserve units, parameters, dependency versions and unsuccessful checks.

## Delivery: editable sources and compatibility

Preserve: GP script and output. Record products, sources and reports separately in `delivery.files` and `delivery.components`. A recipe or export does not replace a requested native project. Reopen the exact saved files, relocate the complete source package and rerun the documented operation. State native CLI, GUI and visual checks separately; never claim a check that did not run.

For learning, retain general, evidenced improvements rather than customer facts. Technical tool-operation lessons require a reproducible test; high-level production methods require the user's acceptance. Never retain secrets or private project data as reusable experience.

Upstream: https://pari.math.u-bordeaux.fr
