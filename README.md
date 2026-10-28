# RigHaven (`righaven`)

> **The Evolving Agent Harness & Open-Source CLI Environment Integrator**

[![Edition](https://img.shields.io/badge/Edition-Community%20%7C%20Cloud-0ea5e9)](#dual-execution-model-cloud-vs-self-hosted-community-edition)
[![i18n](https://img.shields.io/badge/i18n-EN%20(Default)%20%7C%20IT%20(100%25)-10b981)](#native-internationalization-i18n)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

**RigHaven** is an open-source multi-agent orchestration harness and on-demand CLI environment integrator. It is engineered around a dual architectural metaphor:

1. **A Safe Home (The Agent Harness)**: A persistent, supervised orchestration control plane where a lead coordinator plans outcomes (`harness_plan`), clarifies decisive ambiguities (`ask_clarification`), compiles dynamic project-specific roles, manages shared CPU/RAM cgroup budgets, and verifies every deliverable before promotion.
2. **An On-Demand Toolbox (The Ephemeral Sandbox & Community Gallery)**: Rootless, network-sealed ephemeral worker containers (`worker-sandbox`) preconfigured with 37+ audited open-source CLI tools (`typst`, `d2`, `structurizr`, `bpmn`, `pandoc`, `ffmpeg`, `blender`, `freecad`, `playwright`, `calibre`, `manim`, `ifcopenshell`, `trivy`, `opengrep`, and more) plus dynamically mountable **Environment Packs** from the **RigHaven Hub (Community Gallery)**.

## Dual Execution Model: Cloud vs. Self-Hosted Community Edition

Inspired by **n8n**, RigHaven runs from a single codebase supporting two execution modes controlled via `RIGHAVEN_EDITION=community|cloud`:

| Capability | RigHaven Community Edition (`RIGHAVEN_EDITION=community`) | RigHaven Cloud Portal (`RIGHAVEN_EDITION=cloud`) |
| :--- | :--- | :--- |
| **Deployment Target** | Local workstation or self-hosted VPS via Docker Compose | Multi-tenant SaaS Cloud Portal |
| **Authentication** | Local Admin HTTP / Session Auth | Full Sign-Up, JWT Login, OAuth2 (GitHub & Google), Password Recovery |
| **Workspace Isolation** | Single-owner shared `/mnt/user-data` (`righaven-data`) | Per-tenant isolated `/mnt/user-data/tenants/<user_id>` |
| **LLM Provider Keys** | Local `/righaven-state/credentials` | Per-tenant Encrypted API Key Vault (`/api/v1/cloud/vault`) |
| **LLM Providers Supported** | OpenAI Codex (`app-server`), Google Antigravity (`agy`), DeepSeek API, OpenAI-compatible | OpenAI Codex (`app-server`), Google Antigravity (`agy`), DeepSeek API, OpenAI-compatible |
| **Resource Supervision** | Host-aware shared cgroup CPU/RAM budget | Per-tenant execution quotas (`sandbox-minutes`, `storage`, `tokens`) + cgroups |
| **Community Gallery Access** | Full browse, on-demand pack activation, and local/remote publishing | Full browse, one-click activation, Star, Fork, and verified Creator Profile |
| **UI Localization (i18n)** | Native English (`en` default) + Italian (`it` 100%) | Native English (`en` default) + Italian (`it` 100%) |

## 60-Second Quickstart (Docker Compose)

```bash
# 1. Clone the repository and configure your environment
cp .env.example .env
# Set a strong RIGHAVEN_PASSWORD (at least 16 characters) and choose RIGHAVEN_EDITION=community or cloud
sed -i 's/^RIGHAVEN_PASSWORD=.*/RIGHAVEN_PASSWORD=righaven-local-admin-secret-2026/' .env

# 2. Launch the 6-container core stack
bash righaven.sh up

# 3. Open the RigHaven Console
# Web UI:          http://localhost:2026
# Harness Control: http://localhost:2026/workspace/harness
# Gallery Hub:     http://localhost:2026/workspace/gallery
# Cloud Portal:    http://localhost:2026/workspace/cloud
```

## The 6 Core Containers (C4 Container Architecture)

1. **`proxy` (Caddy Edge Gateway)**: TLS termination, HTTP/HTTPS routing, WebSockets/SSE streaming (`flush_interval -1`), and load balancing across Frontend, Gateway, and Cloud Portal.
2. **`frontend` (Next.js / React 19 + TypeScript)**: Interactive multi-agent workspace featuring live artifact preview (Markdown, SVG/PNG, PDF, video/audio, interactive Excalidraw & BPMN 2.0 editors), **Community Gallery**, **Cloud Portal**, and persistent **`EN | IT` language switcher**.
3. **`gateway` (FastAPI Python 3.12 / Core Orchestrator)**: Manages user brief intake, `ask_clarification`, adaptive planning (`harness_plan`), dynamic role compilation, Gallery pack injection, task delegation (`harness_delegate` / `harness_delegate_batch`), and native LLM drivers (**OpenAI Codex**, **Google Antigravity CLI `agy`**, **DeepSeek REST API**).
4. **`redis` (Redis 7.4 State & Event Broker)**: FIFO job admission queues, distributed locking (`distlock`), and Pub/Sub for real-time SSE telemetry.
5. **`runtime-docker` (Isolated Docker-in-Docker Controller)**: Security mediator over `unix:///runtime/docker.sock`. Spawns ephemeral `worker-sandbox` containers with strict cgroups (`--memory`, `--cpus`, `--pids-limit=256`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`), mounts volumes with least privilege, and destroys containers upon job completion.
6. **`worker-sandbox` (Ephemeral Tool & Skill Container)**: Rootless Debian Bookworm container with 37+ open-source CLIs and dynamic mounting of **Community Gallery Environment Packs**.

## Volume Isolation & Formal BPMN 2.0 Resilience Cycle

- **`righaven-data` (`/mnt/user-data`)**: Mounted **Read-Only** inside every `worker-sandbox` and **Read-Write** exclusively by the `gateway` during atomic post-verification promotion.
- **Single-Job Staging (`outputs/workspace/rh-job-<id>` & `RIGHAVEN_OUTPUT_DIR`)**: The only writable directory inside an active sandbox.
- **`righaven-state` (`/righaven-state` & `.righaven-project/`)**: Stores persistent project state, hash-verified request manifests, compiled role skills, and encrypted credentials.
- **Resilience & Reopen Verification Protocol**:
  - **Heartbeats & Incremental State**: Workers emit continuous 2-second heartbeats and save incremental `work/checkpoint.json` (`completed`, `files`, `remaining`, `next_action`) and `work/method.json` (`approach`, `steps`, `scripts`, `limits`).
  - **Surgical Revision (`revise_step_id`)**: When a check or quality review fails, `harness_plan(revise_step_id=...)` reopens only the affected step using diagnostic logs and preserved partial artifacts, never restarting the entire workflow from scratch.
  - **Mandatory `reopen check`**: Before generating `handoff.json`, every editable source (`.typ`, `.dsl`, `.d2`, `.bpmn`, `.blend`, `.FCStd`, `.ifc`, `.docx`, `.xlsx`, `.scraft`) must be copied to a clean directory and independently reopened/recompiled to prove portability.

## Community Gallery ("RigHaven Hub") & `righaven-pack.json`

The RigHaven Hub organizes community and built-in capabilities into three categories:
1. **`environment`**: Declarative sandbox rigs (*Architecture & Modeling Rig*, *Media & FFmpeg Mastering Rig*, *Full-Stack Web Scraper & QA Rig*, *Data Science & Typst Publishing Rig*, *Parametric CAD & 3D Geometry Rig*).
2. **`cli-tool`**: Standardized wrappers for 37+ open-source CLI tools with safe flags and automated health checks.
3. **`skill`**: Competency modules (`skill-typst`, `skill-c4-structurizr`, `skill-d2`, `skill-bpmn`, `skill-pandoc`, `skill-ffmpeg`, etc.) that teach agents how to combine CLIs and verify editable sources.

### Creating & Publishing a Pack (`righaven-pack.json`)

```json
{
  "id": "skill-custom-diagram",
  "name": "Custom Architecture Diagram Skill",
  "version": "1.0.0",
  "author": "your-handle",
  "category": "skill",
  "i18n": {
    "en": {
      "title": "Custom Architecture Diagrammer",
      "description": "Produces verified C4 and D2 diagrams with portable sources."
    },
    "it": {
      "title": "Diagrammatore Architetturale Personalizzato",
      "description": "Produce diagrammi C4 e D2 verificati con sorgenti portabili."
    }
  },
  "docker_dependencies": {
    "base_image": "righaven-sandbox:0.1.0",
    "system_packages": ["graphviz"],
    "python_packages": [],
    "node_packages": []
  },
  "cli_binaries": [
    {
      "name": "d2",
      "executable": "/usr/local/bin/d2-cli",
      "safe_flags": ["--layout=elk"],
      "health_check": "craft capabilities d2"
    }
  ],
  "skill_prompt_template": "Write .d2 sources inside $RIGHAVEN_OUTPUT_DIR, render SVG/PNG, and verify independent reopen in a clean folder before saving handoff.json.",
  "verification_command": "craft capabilities d2",
  "security_policy": {
    "rootless": True,
    "network_access": False,
    "writable_paths": ["$RIGHAVEN_OUTPUT_DIR"],
    "read_only_mounts": ["/mnt/user-data"]
  }
}
```

Publish via REST API or the Gallery UI:
- `GET /api/v1/gallery/packs` — Browse, search, and filter packs (`category`, `q`, `tag`, `Accept-Language: en|it`).
- `POST /api/v1/gallery/packs/{id}/activate` — Activate on-demand in workspace or inject into `harness_plan`.
- `POST /api/v1/gallery/packs/publish` — Validate against `config/righaven-pack.schema.json` and publish.

## Native Internationalization (i18n)

- **Frontend Dictionaries**: `/locales/en/common.json` (Default) and `/locales/it/common.json` (100% parity), mirrored in `/frontend/locales/`.
- **Automatic Detection & Navbar Selector**: Detects browser locale with fallback to `en` and provides an `EN | IT` toggle across the Dashboard, Gallery, and Cloud Portal.
- **Backend Localization**: `gateway` inspects `Accept-Language` (`en` or `it`) to localize system notifications, status updates, and `ask_clarification` prompts while keeping all internal code, identifiers, and logs in English.

## Architectural Diagrams & Technical Documentation

- [Audit & Legacy Mapping (`docs/AUDIT_AND_MAPPING.md`)](docs/AUDIT_AND_MAPPING.md)
- [C4 Model in Structurizr DSL (`docs/c4/righaven.dsl`)](docs/c4/righaven.dsl)
- [C4 System Context in D2 (`docs/c4/righaven_context.d2`)](docs/c4/righaven_context.d2)
- [C4 Containers & Volumes in D2 (`docs/c4/righaven_containers.d2`)](docs/c4/righaven_containers.d2)
- [BPMN 2.0 Coordination Cycle (`docs/bpmn/coordination_cycle.bpmn`)](docs/bpmn/coordination_cycle.bpmn)
- [Typst Technical Report (`docs/technical-report.typ`)](docs/technical-report.typ)
- [Contributing Guide (`CONTRIBUTING.md`)](CONTRIBUTING.md) & [Code of Conduct (`CODE_OF_CONDUCT.md`)](CODE_OF_CONDUCT.md)
