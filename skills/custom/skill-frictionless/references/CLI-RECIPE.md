# Generate and verify a tabular contract

Run in the staging directory for the delivery. Inspect descriptors from third parties before validation. Resolve resources only within the local delivery and avoid loading remote resources or plugins.

```sh
frictionless describe sales.csv --type package --json > datapackage.json
# Review and update the descriptor to match the agreed data contract.
frictionless validate datapackage.json --json > validation.json
```

Check the exit status and the report's `valid` field. Read errors under each task. Copy the package and resources into an isolated folder and repeat validation using the same tool version. Include the contract and the validation evidence in the delivery.
