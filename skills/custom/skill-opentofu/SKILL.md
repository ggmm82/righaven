---
name: skill-opentofu
description: "Validate OpenTofu modules and produce reviewable infrastructure plans using isolated fixtures or an authorized target."
---

# OpenTofu

Use OpenTofu when the deliverable includes infrastructure as code, modules or a plan for review. Use TFLint for policy and provider-specific linting. Review the source, required provider versions and backend before initialization. Untrusted modules and providers must be reviewed before loading them.

Start with a copied project, synthetic variables and a local fixture. For configuration validation run `tofu init -backend=false -input=false` and then `tofu validate -json`. Initialization can still download modules and providers. For an offline demonstration, use a local configuration containing only the built-in `terraform_data` resource. Add remote planning only when the user specifies the target and its approved credentials. Keep changes to live infrastructure, state and credentials outside the validation assignment.

## Delivery: editable sources and compatibility

Deliver the editable `.tf` module, sample inputs with synthetic values, provider lock file if generated, and a validation report. Summarize creates, updates, replacements and deletions with their reasons. Review the summary for secrets, account identifiers and sensitive values. Treat saved plans and state as sensitive, since they can contain raw input values. Document the OpenTofu version, provider constraints and the assumptions behind the plan.

See the [CLI recipe](references/CLI-RECIPE.md), [capability map](references/CAPABILITIES.md) and [quality checklist](references/QUALITY.md).
