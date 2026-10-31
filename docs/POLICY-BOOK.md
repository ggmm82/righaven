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
organization sheets are stored under `$RIGHAVEN_STATE/policy-book/` with their
draft, published versions and history.

| Field | Meaning |
|---|---|
| `id`, `title`, `summary` | Identity; `id` is lowercase letters, digits and `_` (max 40). `version` is assigned on publication |
| `mandatory` | Always included in every Policy Plan |
| `rules` | Constraints injected into each applicable assignment |
| `handoff_checks` | Checks the specialist must declare in `handoff.json` with `policy_check: "<sheet>.<check>"` |
| `final_checks` | Criteria of the final validation (`id`, `requirement`, `method`, `critical`, optional `probe`), or `"acceptance"` |
| `depends_on` | Sheets that must pass before this one is validated |
| `applies_to` | Assignment purposes that receive the rules (default: work, preview, integration, delivery) |

Each sheet has a content `revision`. A Policy Plan pins a copy of the sheets it
selected, so later edits to the book do not change a running project; a sheet
made mandatory later is added to existing plans.

### Executable probes

A final check may name a `probe` from a closed catalog. `harness_validate` runs it
before any review, on the exact product file, in a container prepared with that
catalog tool: no network, no capabilities, read-only root, the file mounted
read-only, 300 s limit. The outcome is stored with the product SHA-256, so a
corrected version is probed again and an unchanged one is not.

| Probe | Tool | Files | Passes when |
|---|---|---|---|
| `pdf_structure` | qpdf | PDF | `qpdf --check` reports no damage |
| `pdf_text` | poppler | PDF | `pdftotext` extracts at least one word |
| `pdfa_conformance` | veraPDF | PDF | veraPDF reports `PASS` for the declared PDF/A profile |
| `media_streams` | ffmpeg | audio/video | `ffprobe` finds a decodable audio or video stream |
| `no_secrets` | gitleaks | any | `gitleaks dir` finds no secret (values redacted) |

A failed critical probe fails the sheet, with the program's evidence among the
findings. A failed non-critical probe is recorded as evidence. Probe checks are
left out of the reviewer's contract; a sheet made only of probes needs no
reviewer. The wizard offers the probes under "Automatic check".

## Managing sheets

Administrators manage the book under **Configuration → Policy Book**; other users
read every sheet there. New sheets and new versions use a guided setup in six
steps, each explaining its choices: purpose and when the policy applies
(always, or when the coordinator finds it relevant), working rules, checks
specialists declare during work (blocking or recorded), final verification
(the project acceptance review or the sheet's own criteria with a readable
verification method), the assignments that receive it and the policies to verify
first, then a plain-language summary before saving a draft or publishing. Check
codes are generated from the text.

Organization sheets follow a lifecycle:

| State | Meaning |
|---|---|
| Draft | Being written; not offered to projects. Never-published drafts can be deleted. |
| Active | Its active version is offered to new Policy Plans (mandatory sheets are always added). |
| Retired | No longer offered; projects that pinned it keep validating that version. Reactivation restores it. |

Editing an active sheet saves a separate draft: the active version keeps applying
until the draft is published. Publishing freezes the draft as the next immutable
version (v1, v2, …) after checking its dependencies. Any published version can be
restored as a draft. Every operation is recorded with its author and time. A sheet
other active sheets depend on cannot be retired; built-in sheets are read-only.

## The user in the loop

- **Tool alternatives.** When several catalog tools could produce the result, the
  brief records `tool_options`: two to four alternatives with programs, pros, cons
  and a motivated recommendation. Production waits for the user's choice, which
  can only be recorded after a new user message; roles using programs of rejected
  alternatives are refused.
- **A pause after every phase.** When a production assignment completes with a
  result, further production waits until the user replies: the coordinator
  presents results, open issues and next steps and proposes plan changes. Reviews
  and final validation do not pause. The owner can turn pauses off per project
  from the Policy line.

Every conversation shows a **Policy** line under the project title. It is
recomputed from the recorded reviews at each refresh and expands to the governance
phase, when the Policy Plan was pinned and by whom, each sheet with its version
and why it applies, the handoff checks declared by the assignments, the verdict
on the current product with the date of the review, every criterion not passed or
not verified with its evidence, and the next step. **Project details** shows the
same view expanded.

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
| `GET` | `/api/harness/policy-book` | Users with `agents:read`; `can_manage` tells whether the caller is an administrator |
| `GET` | `/api/harness/policy-book/sheets/{id}` | Users with `agents:read`: draft, published versions and history |
| `PUT` | `/api/harness/policy-book/sheets/{id}/draft` | Administrators: create a sheet or save its next draft |
| `DELETE` | `/api/harness/policy-book/sheets/{id}/draft` | Administrators: discard the draft (deletes a never-published sheet) |
| `POST` | `/api/harness/policy-book/sheets/{id}/publish` · `retire` · `reactivate` | Administrators |
| `POST` | `/api/harness/policy-book/sheets/{id}/restore` with `{"version": n}` | Administrators: copy a published version into the draft |

## Compatibility

Projects created before the Policy Book report `governance.phase = legacy` and
keep their previous checks, so conversations in progress are not interrupted.
