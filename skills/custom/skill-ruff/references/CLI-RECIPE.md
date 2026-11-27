# Check Python and notebook deliveries

Use the applicable project configuration, from a directory that contains the intended configuration and source files.

```sh
ruff check --output-format json src notebooks > ruff-report.json
ruff format --check src notebooks
ruff rule F821
```

Review diagnostics before making changes in staging. Rerun the same checks after edits and record version, scope and exit statuses in the delivery. Run automated tests separately for execution evidence.
