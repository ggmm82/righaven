# RigHaven Canonical Architecture & Nomenclature Specification

This document specifies the canonical **RigHaven** (`righaven`, `rh-`, `harness_`) nomenclature across packages, volumes, environment variables, orchestration tools, and REST API routes.

## 1. Core Package & Directory Structure

| RigHaven Path | Category | Purpose |
| :--- | :--- | :--- |
| `righaven/` | Core Backend Package | FastAPI Gateway, Multi-Agent Orchestrator, Community Gallery, Cloud Portal, and i18n |
| `righaven.sh` | CLI Entrypoint Script | Build, launch, stop, inspect logs, and execute full validation & unit test suites |
| `config/righaven.yaml` & `righaven/righaven.yaml` | Orchestrator Configuration | Model profiles (`rh-codex`, `rh-squad`), tool groups (`harness`), and custom agents |
| `config/righaven-pack.schema.json` | Gallery Schema | JSON Schema for `righaven-pack.json` manifests |
| `config/gallery-packs.json` | Gallery Catalog | Default catalog of 84+ Environment Rigs, Open-Source CLI Tools, and Agent Skills |
| `scripts/install_righaven.py` | Sandbox Tool Installer | Checksum-verified installer for sandbox CLI applications |
| `frontend/harness-page.tsx` | Frontend Harness Console | Harness administration and provider configuration view |
| `frontend/gallery-page.tsx` | Frontend Gallery UI | Community Gallery exploration, activation, and pack publishing view |
| `frontend/cloud-portal-page.tsx` | Frontend Cloud Portal UI | Multi-tenant Sign-Up/Login, OAuth2, Encrypted Vault, and Quotas view |
| `frontend/i18n.tsx` & `locales/{en,it}/common.json` | Native i18n System | English (`en` default) and Italian (`it` 100% parity) localization dictionaries |
| `skills/custom/skill-harness/` | Coordinator Protocol Skill | Multi-agent role compilation and adaptive planning instructions |
| `skills/custom/skill-workspace/` | Workspace & Handoff Skill | Staging isolation, reopen check, and `handoff.json` contract |
| `skills/custom/skill-<tool>/` (37 tools) | Agent Tool Skills | Competency modules and `righaven-pack.json` manifests for all 37 CLI tools |

## 2. Volumes, Directories & Isolation Boundaries

| RigHaven Identifier | Scope & Mount Policy |
| :--- | :--- |
| Volume `righaven-data` (`/mnt/user-data`) | Mounted Read-Only (`ro`) for `worker-sandbox` and Read-Write (`rw`) for `gateway` promotion |
| Volume `righaven-state` (`/righaven-state`) | Persistent installation state, encrypted credentials, Gallery store, and Cloud tenant records |
| `.righaven-project/` | Per-workspace locked project state, request manifests, and compiled role skills |
| `.righaven-jobs/` | Per-job live telemetry, resource leases, and 2-second heartbeat records |
| `outputs/workspace/rh-job-<id>` | Isolated single-job staging directory (`RIGHAVEN_OUTPUT_DIR`) |
| `/mnt/user-data/tenants/<user_id>` | Isolated multi-tenant workspace in `RIGHAVEN_EDITION=cloud` mode |

## 3. Environment Variables

| RigHaven Variable | Description |
| :--- | :--- |
| `RIGHAVEN_EDITION` | Execution mode: `community` (Self-Hosted Open Source) or `cloud` (Multi-Tenant Cloud Portal) |
| `RIGHAVEN_DEFAULT_LOCALE` | Default localization language (`en` default, `it` preset) |
| `RIGHAVEN_OUTPUT_DIR` | Sole writable path inside `worker-sandbox` (`outputs/workspace/rh-job-<id>`) |
| `RIGHAVEN_ISOLATED_OUTPUT` | Enforces gateway-only finalization and atomic promotion |
| `RIGHAVEN_JOB_DEADLINE` | Bounded execution deadline timestamp per delegated phase |
| `RIGHAVEN_CPU_THREADS` & `RIGHAVEN_MEMORY_MIB` | Sandbox cgroup CPU thread and RAM allocation limits |
| `RIGHAVEN_SANDBOX_IMAGE` | Pinned worker sandbox image digest (`righaven-sandbox:0.1.0`) |
| `RIGHAVEN_STATE` | Persistent state mount path (`/righaven-state`) |
| `RIGHAVEN_PASSWORD` & `RIGHAVEN_USER` | Gateway & Proxy authentication credentials |
| `RIGHAVEN_PUBLIC_URL`, `RIGHAVEN_DOMAIN`, `RIGHAVEN_BIND_IP` | Network binding and public URL configuration |
| `RIGHAVEN_ENVIRONMENT_MODE` & `RIGHAVEN_DOCKER_SCOPE` | Dynamic environment preparation and internal Docker daemon scope |
| `RIGHAVEN_CONFIG_PATH` & `RIGHAVEN_HOME` | Core configuration and runtime home directory |
| `RIGHAVEN_STREAM_BRIDGE_REDIS_URL` | Redis 7.4 Pub/Sub and SSE stream bridge URL |

## 4. Orchestrator Tools & REST API Routes

| RigHaven Tool / Route | Description |
| :--- | :--- |
| `harness_plan` | Operational planning (`outcome`, `criteria`, `roles`, `revise_step_id`) |
| `harness_delegate` & `harness_delegate_batch` | Single and concurrent FIFO-queued sandbox delegation |
| `harness_skills` & `harness_read_context` | Skill discovery and hash-verified context pagination |
| `harness_lessons` | Conditional lesson extraction and runtime verification |
| `/harness/api/*` | Harness configuration, LLM providers, and runtime budget API |
| `/api/harness/environments/*` | On-demand and preloaded environment lifecycle API |
| `/api/harness/tool-versions/*` | Verified CLI tool release management API |
| `/api/threads/{id}/harness-*` | Thread jobs, audit log, guide, designs, and delivery acceptance |
| `GET /api/v1/gallery/packs` | Browse, search, and filter the Community Gallery |
| `POST /api/v1/gallery/packs/{id}/activate` | On-demand pack activation and `harness_plan` injection |
| `POST /api/v1/gallery/packs/publish` | Schema-validated community pack publishing |
| `/api/v1/cloud/*` | Multi-tenant Cloud Portal Auth, Vault, Quotas, and Creator APIs |
| `/api/v1/i18n/*` | Native `en` / `it` dictionary and `Accept-Language` resolution API |
