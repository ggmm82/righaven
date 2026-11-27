---
name: skill-ruff
description: "Lint and format editable Python code and Jupyter notebooks with Ruff. Report concrete diagnostics and preserve notebook content."
---

# Ruff

Use Ruff to lint Python source and notebook code cells and to check formatting. Honor the project's checked-in configuration and the intended Python version. Limit checks to the files relevant to the assignment. Run read-only checks first. Make edits in staging and review the diff, especially for notebooks and imports. Keep unsafe fixes disabled unless a specific change has been reviewed and is explicitly needed.

## Delivery: editable sources and compatibility

Deliver the edited `.py` and `.ipynb` files, applicable Ruff configuration and the final lint evidence. Preserve markdown, metadata and outputs unless editing them was part of the request. Run project tests or execute notebooks separately when required to substantiate behavior.

See [the CLI recipe](references/CLI-RECIPE.md), [capabilities](references/CAPABILITIES.md) and [quality checks](references/QUALITY.md).
