# Policy Book and policy-driven execution

RigHaven governs every new project with an organization **Policy Book**. The
runtime, not the coordinator's prompt, enforces the lifecycle:

```text
Brief -> Execution Plan + Policy Plan -> policy-aware assignments
      -> final multi-policy validation -> delivery
```

`governance.phase` in the project (`briefing`, `planning`, `execution`,
`validation`, `delivery`, `delivered`) is derived from recorded facts.

## Policy Sheets

A sheet is declarative JSON. Built-in sheets ship in `righaven/policy-book.json`;
organization sheets are stored under `$RIGHAVEN_STATE/policy-book/` and edited by
administrators.

| Field | Meaning |
|---|---|
| `id`, `title`, `version`, `summary` | Identity; `id` is lowercase letters, digits and `_` (max 40) |
| `mandatory` | Always included in every Policy Plan |
| `rules` | Constraints injected into each applicable assignment |
| `handoff_checks` | Checks the specialist must declare in `handoff.json` with `policy_check: "<sheet>.<check>"` |
| `final_checks` | Criteria of the final validation (`id`, `requirement`, `method`, `critical`), or `"acceptance"` |
| `depends_on` | Sheets that must pass before this one is validated |
| `applies_to` | Assignment purposes that receive the rules (default: work, preview, integration, delivery) |

Each sheet has a content `revision`. A Policy Plan pins a copy of the sheets it
selected, so later edits to the book do not change a running project; a sheet
made mandatory later is added to existing plans.

The default sheet `quality_standard` (*Revisione di qualità standard*) is
mandatory and uses `final_checks: "acceptance"`: it is satisfied by the existing
separate quality review against the project's acceptance contract.

Example organization sheet:

```json
{
  "id": "security",
  "title": "Sicurezza",
  "rules": ["Non inserire credenziali o token nei file consegnati."],
  "handoff_checks": [{"id": "no_secrets", "requirement": "Nessuna credenziale nei file prodotti"}],
  "final_checks": [{"id": "secret_scan", "requirement": "Il prodotto non contiene credenziali", "method": "technical"}]
}
```

## Lifecycle enforcement

1. **Briefing.** Unchanged: assignments wait until the intended result and
   delivery form are settled.
2. **Planning.** The coordinator defines the Execution Plan (`steps_json`, roles)
   and the Policy Plan with `harness_plan(policies_json=...)`: optional sheets with
   a `reason` and optional `steps` scope, or `[]`. Mandatory sheets are added by the
   runtime. When the book offers no optional sheet, the runtime records the plan
   itself. Production assignments are refused until the Policy Plan is settled.
3. **Execution.** Each assignment receives the rules of the sheets that apply to
   its activity and purpose. After the worker returns, missing or failed critical
   `handoff_checks` put the activity in `needs_revision` and are reported as
   `policy_violations`.
4. **Validation.** `harness_validate(role_id=...)` runs on the finished product: a
   delivery integrity check, then one separate review per sheet without a valid
   verdict for the exact file hash. Independent sheets run in parallel; dependent
   sheets run after their prerequisites pass. Results are aggregated in one reply
   and stored as `policy_validation`. Reviews of organization sheets are judged by
   the worker against that sheet's contract (`policy_review` in the job).
5. **Delivery.** `harness_plan(status=ready)` and automatic completion recompute the
   validation from files and refuse delivery unless every sheet passed. When the
   owner accepts a version directly, the policy verdicts at that moment are stored
   in `user_acceptance`.

Plan definition, handoff violations and validation outcomes are written to the
conversation audit journal with the actor `Policy Book`.

## API

| Method | Path | Access |
|---|---|---|
| `GET` | `/api/harness/policy-book` | Users with `agents:read` |
| `PUT` | `/api/harness/policy-book/sheets/{id}` | Administrators |
| `DELETE` | `/api/harness/policy-book/sheets/{id}` | Administrators; built-in sheets and sheets other sheets depend on cannot be deleted |

## Compatibility

Projects created before the Policy Book report `governance.phase = legacy` and
keep their previous checks, so conversations in progress are not interrupted.
