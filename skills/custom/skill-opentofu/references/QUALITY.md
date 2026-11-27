# Infrastructure delivery review

- Confirm the intended target, provider and OpenTofu versions, and variable assumptions.
- Validate in a copied directory with the recorded dependencies. Describe any validation that requires network or real target access.
- Review replacements and deletions individually, with reasons and affected resources.
- Share editable modules and sample inputs. Scrub credentials and sensitive plan values before sharing reports.
- Record whether the checks covered a local fixture or a plan for an explicitly authorized remote target.
