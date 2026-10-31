#set page(paper: "a4", margin: (x: 2cm, y: 2.2cm))
#set text(font: "Liberation Sans", size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.65em)

#align(center)[
  #text(size: 20pt, weight: "bold")[RigHaven (`righaven`) Architecture & Migration Report]
  #v(0.4em)
  #text(size: 12pt, style: "italic")[The Evolving Agent Harness & Open-Source CLI Environment Integrator]
  #v(0.4em)
  #text(size: 9.5pt)[Version 1.0.0 — Community Self-Hosted & Multi-Tenant Cloud Portal Architecture]
]

#v(1em)

= 1. Executive Summary & Architectural Vision

*RigHaven* (`righaven`) combines two complementary engineering paradigms into a unified open-source platform:
1. *Safe Home (The Agent Harness)*: A stateful, fault-tolerant multi-agent control plane (`gateway` + `redis` + `runtime-docker`) that receives user briefs, resolves ambiguities via `ask_clarification`, compiles dynamic project roles (`harness_plan`), enforces cgroup resource budgets, and validates deliverables before atomic promotion.
2. *On-Demand Toolbox (The Ephemeral Sandbox & Community Gallery)*: Assignment worker containers with all capabilities dropped, `no-new-privileges`, PID/CPU/memory limits, per-job credential copies and bridge networking (or, with `RIGHAVEN_WORKER_EGRESS=allowlist`, an internal network behind a per-job domain allowlist proxy). They read the project read-only, write only to their staging folder, and use prepared images built from a catalog of 62 managed CLI tools and Gallery environment packs (`righaven-pack.json`).

= 2. The 6 Core Containers & Volume Isolation

#table(
  columns: (auto, 1fr, 2fr),
  inset: 6pt,
  [*Container*], [*Technology*], [*Architectural Responsibility*],
  [`proxy`], [Caddy 2.10], [TLS termination, HTTP/HTTPS routing, and real-time SSE streaming.],
  [`frontend`], [Next.js / React 19], [Interactive workspace, artifact previewer, Community Gallery UI, Cloud Portal UI, and native `EN | IT` i18n selector.],
  [`gateway`], [FastAPI Python 3.12], [Core orchestrator (`harness_plan`, `harness_delegate`), Gallery REST API, Cloud Multi-Tenant Auth/Vault, and `Accept-Language` localization.],
  [`redis`], [Redis 7.4], [FIFO execution queues, distributed locking (`distlock`), and SSE Pub/Sub telemetry.],
  [`runtime-docker`], [Docker-in-Docker], [Security mediator over `unix:///runtime/docker.sock` enforcing CPU/RAM/PID cgroups and least-privilege mounts.],
  [`worker-sandbox`], [Debian Bookworm], [One container per assignment with capabilities dropped and resource limits, running prepared images from 62 managed CLI tools and Gallery environment packs.]
)

- *Workspace Data Volume (`righaven-data` / `/mnt/user-data`)*: Mounted *Read-Only* inside `worker-sandbox` and *Read-Write* only for final Gateway consolidation.
- *Single-Job Staging (`outputs/workspace/rh-job-<id>` / `RIGHAVEN_OUTPUT_DIR`)*: The sole path writable by an active worker sandbox.
- *State Volume (`righaven-state` / `.righaven-project/`)*: Stores locked project state, encrypted credentials, and Gallery pack activations.

= 3. Formal BPMN 2.0 Resilience & Reopen Verification Protocol

Every delegated task follows a strict verification lifecycle:
- *Incremental Checkpointing*: Workers emit 2-second heartbeats and persist `work/checkpoint.json` and `work/method.json`.
- *Surgical Revision (`revise_step_id`)*: Failed checks trigger targeted step reopening via `harness_plan(revise_step_id=...)` without discarding validated upstream artifacts.
- *Mandatory `reopen check`*: Before generating `handoff.json`, editable sources must be transferred to an isolated directory and reopened/compiled independently.

= 4. Community Gallery (`righaven-pack.json`) & Dual Edition (`community` | `cloud`)

The *RigHaven Hub* exposes 84+ built-in packs across `environment`, `cli-tool`, and `skill` categories via:
- `GET /api/v1/gallery/packs` — Search and filter localized (`en` / `it`) manifests.
- `POST /api/v1/gallery/packs/{id}/activate` — Activate on-demand in the workspace and inject into `harness_plan`.
- `POST /api/v1/gallery/packs/publish` — Validate against `config/righaven-pack.schema.json` and publish to the community registry.

When `RIGHAVEN_EDITION=cloud`, the platform enables `/api/v1/cloud/*` endpoints providing JWT + OAuth2 (GitHub/Google) authentication, per-tenant workspaces (`/mnt/user-data/tenants/<user_id>`), an encrypted API Key Vault, and execution quotas (`sandbox_minutes`, `storage_bytes`, `tokens`).
