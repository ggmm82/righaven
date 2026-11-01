# Recipes and guided projects

RigHaven uses three building blocks with one vocabulary:

| Block | Answers | Where |
|---|---|---|
| **Skill** | *how* to work: method, quality checks, expertise on a tool | Tools & skills |
| **Environment** | *with which tools*: programs prepared on first use and reused | Environments |
| **Recipe** | *which path*: phases and owner approvals that combine skills and an environment for a kind of result | Recipes |

A recipe is a reusable project method, offered through a guided intake. The intake asks for the goal and accepts, at once, the schema definition and documents
(DDL/SQL, PDF, Word, Excel, CSV, JSON, XML, Parquet…), links to external documentation and the
registered connections to assign to the task; everything else is optional. Users describe the desired outcome in ordinary language. Unknown source engines, deployment targets, BI tools and frequencies may be left empty. Attach documents in the resulting native conversation; the coordinator must read them before asking at most three decisive questions.

## Persistent workflow

The selected recipe version, answers, phases, activity bindings and evidence hashes are stored in the thread workspace. Opening or refreshing the conversation restores the same state. Start and read requests use the native thread owner checks. Updates and decisions require the observed revision, preventing lost updates from multiple tabs.

The existing project plan owns dynamic roles and assignments. A journey does not introduce a second scheduler or a user-facing programming language. `harness_journey` reads the selected method, links phases to native activities and submits saved artifacts for review. It cannot approve its own output. The owner approves, revises or skips individual phases from the project card. Changed evidence invalidates dependent results without deleting files.

Starting a guided data project pins its release policy alongside organization policies, without adding data-specific obligations to other projects or replacing administrator policies, including imported recipe templates. Final delivery requires the guided phases and the existing quality review to pass. A policy is not a substitute for executing its checks.

## Owner decisions in the project card

The project card above the chat shows the path: recipe, settled phases and the current phase. When
a phase waits for the owner, a **Your turn** box appears directly in the card with the saved
results and three buttons: **Approve phase**, **Request changes** (with a note) and **Skip phase**.
The coordinator never asks for approval as a chat question, and a chat reply never approves a
phase. *All phases* opens the **Path** tab with every phase, its result and notes; a skipped phase
can be resumed there.

- **Skip.** A phase that adds nothing to the goal (for example replica and package for a demo with
  sample data) can be skipped by the owner. A skipped phase satisfies its dependants and stays
  skipped when earlier results change, until the owner resumes it.
- **Proposals.** At the first turn the coordinator compares the goal with every phase and proposes
  skipping, with a reason, all the phases the goal does not need, including later ones
  (`harness_journey(propose_skip=true)`). The card shows them together with **Skip these phases** and
  **Keep them all**; *All phases* lets the owner choose one by one. Only the owner decides.
- **One goal, one decision channel.** The goal written at the start is the project's result: the
  team does not ask for it again, and the card shows it with what you get at the end. In a guided
  project the phase approvals replace the chat confirmation that free projects ask after each
  production step, so nothing is approved twice. Free projects, started without a recipe, keep
  their brief questions and chat checkpoints unchanged.
- **Phases without approval.** A recipe author can mark technical phases as not needing approval:
  they complete when their results are saved. In the built-in data recipe, *Laboratory* and *Test
  scenarios* work this way; the owner still sees their results.

The coordinator receives a compact view of the path (choices, phase states and result paths), not the
full recipe definition and policy, to keep every turn small.

## Your own recipes

On the Recipes page **New recipe** opens a four-step editor; **Duplicate** copies any visible
recipe, including built-in ones, as a starting point. The steps are *Result* (name, what it
produces, when to use it, what you get, what to attach), *Phases* (each with its result and an
optional stop for approval), *Tools* (choose an environment; suitable skills are proposed) and
*Summary* (a preview of the card plus optional details). A recipe has:

1. **Method · skills**: one to eight skills enabled in your account (methods and tool skills).
2. **Tools · environment**: an environment preset; its tools, plus those of the chosen tool skills,
   become the recipe's tools. Nothing is typed by hand.
3. **Path · phases**: one to twelve phases, each with an expected result and *asks for approval* on or
   off. Phases run in order.
4. **What is needed and what you get**: attachments, questions, outputs and prerequisites shown on
   the recipe card, plus optional directions for the team and keywords the coordinator uses to
   propose the recipe.

Recipes are private to their author until the author **publishes them to the catalog**. Published
recipes appear in the **Community Gallery** (filter *Recipes*, next to environments, CLI tools and
skills), on the Recipes page of every user and in the coordinator's recipe index for accounts that
have its skills enabled. From the Gallery, **Use this recipe** starts the guided intake and **Copy to
my recipes** opens an editable copy. An administrator can withdraw any published recipe. Only the
author edits or deletes a recipe (an administrator may also edit published ones). Projects already started keep the phases pinned at start. Texts are checked for
credentials; use Connections for access. User recipes carry phases and approvals, not organization
policy sheets.

## Data engineering path

1. Read documents; build a catalog with provenance, uncertain relations and business definitions.
2. Agree architecture, extraction semantics, schedules, measures and deployment expectations.
3. Build the local laboratory. Clearly distinguish DuckDB simulation from a faithful replica on the original engine.
4. Generate deterministic synthetic scenarios; test constraints, updates, deletes and anomalies.
5. Verify recurring acquisition and transformations, reconciliation, recovery and repeatability.
6. Deliver actual business reports and editable query/model sources. BI tables or example counts alone do not satisfy reporting.
7. Use `harness_package_check` to build and start the exact exported package in an isolated runtime without production access; verify a second cycle and restart, and deliver evidence and a runbook.

No live connection is needed for the synthetic path. External source and production target checks remain unverified until authorized access is supplied. In-app workers are disposable builders; the exported project's volume retains pipeline and SQLMesh state and reports between container replacements. This release does not turn temporary worker terminals into persistent database or BI servers.

## Exported package

The package includes hashed dependency locks, executable entrypoint, one ordered cycle protected by a shared-storage lock, writable SQLMesh state under DATA_DIR and a consistent warehouse path. Minute ticks respect independent stub/ingestion/transformation schedules recorded in ops/schedules.json; successful job timestamps survive restarts. Full snapshot loads are the safe default; incremental cursors must be explicitly confirmed and tested. The local HTML report renderer runs offline, retaining SQL definitions and actual query results. Production HTML reporting uses an explicitly configured read-only warehouse connection; native BI mode must be chosen explicitly and verified through its adapter. Replace the example counts with agreed KPIs. Native Power BI/Metabase/Superset deployment requires its own adapter and actual target verification.

CI builds the generated Dockerfile, starts the exported scheduler without RigHaven, checks two cycles across container replacement and checks real report output. Technical fixtures do not certify arbitrary customer schema semantics or production credentials.

## Connections and access

The access page discovers the existing model-provider CLI/API connections and the personal database/identity connections. It does not duplicate OAuth sessions or change coordinator/team model assignment. Database grants are optional. Each compiled role declares the subset of owner-authorized connection IDs it needs; document reviewers receive no database credentials by default. Additional connector families require reviewed adapters, not merely new dropdown entries.

## Per-project package verification

`harness_package_check` accepts a bounded package directory from the current conversation outputs. It requires the managed Dockerfile, runtime and dependency locks of the current release. A dedicated BuildKit container and execution worker acquire the shared resource budget. No model credentials or production connections are mounted; execution has no network. Cancellation tears down the builder and worker before capacity is released, with quarantine when cleanup cannot be confirmed.

The report binds the input file hashes to a host-owned verification job. The package phase refuses a hand-written success report or changed package contents. A locally passed report does not certify native Power BI deployment, external accounts or the business meaning of the agreed measures. Those remain separate policy checks.
