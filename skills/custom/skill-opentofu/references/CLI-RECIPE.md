# Validate and review an offline fixture

Work in the assignment staging directory with a reviewed fixture, no explicit backend, and only built-in resources.

```sh
tofu fmt -check -diff
tofu init -backend=false -input=false -no-color
tofu validate -json > validation.json
tofu plan -input=false -refresh=false -no-color -detailed-exitcode
```

The plan exit codes are `0` with no changes, `2` with changes and `1` on error. The fixture uses local state semantics. A production backend or provider can require network access and authorization, even if the operation is only a plan. Prepare the reviewable source delivery with example variables, a reproducible validation command and a plan summary. Keep binary plans and state out of ordinary deliveries.
