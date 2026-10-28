# RigHaven

RigHaven is a home and an on-demand toolbox for agents. It coordinates dynamic
project roles, prepares isolated environments containing open-source CLI tools,
and preserves project state, editable sources and reusable lessons.

## Run the Community edition

Copy `.env.example` to `.env`, set `RIGHAVEN_PASSWORD` to a unique password
of at least 16 characters, then run `bash righaven.sh up`.
Open http://localhost:2026. Build tools require Docker Compose and the private
runtime requires privileged container support. The application does not mount
the host Docker socket. Persistent named volumes preserve application data and
the internal runtime across container replacement.

For Hostinger, use only the Compose attached to a successful verified release.
The GitHub workflow builds images, checks native tools, tests portability and
boots the complete stack before publishing the deployment bundle.

## Architecture

- `core/backend` and `core/frontend`: the checked-in application engine and web workspace.
- `righaven/`: project coordination, runtime supervision, delivery checks and Gallery services.
- `skills/`: operational methods and tool-specific instructions.
- `config/worker-bundle.json`: the trusted code mounted read-only into each job.
- `runtime-docker`: an application-owned daemon with persistent software storage.
- Individual tasks receive isolated staging directories. Only validated outputs
  are promoted into the project.

OpenAI Codex, Antigravity CLI, DeepSeek and custom OpenAI-compatible endpoints
can be configured for the coordinator, specialists or both. Roles are compiled
for the project; an environment supplies capabilities rather than fixing a role.

## Gallery

The Gallery catalogs environments, CLI tools and skills. Activation uses the
signed-in core account. An environment pack creates a native Agent configuration
with on-demand deployment; a skill pack goes through the native skill archive
scanner before it becomes usable. Disabled native tools remain disabled.

Published pack versions are immutable and belong to their publisher.
Community manifests cannot mark themselves verified or overwrite built-in packs.
The current runtime supports tools in its managed catalog; arbitrary executable
or dependency declarations are not installed automatically.

Catalogs can be exported and hosted on HTTPS. Administrators approve remote
catalog URLs with an exact SHA-256 pin from the Gallery interface; synchronization
validates the complete catalog before replacing its local snapshot. Remote pack
identifiers are namespaced and cannot overwrite local or built-in capabilities.
The hash pin authenticates approved catalog bytes; it is not a publisher signature.
A public hosted directory, publisher signatures and automatic installation of
arbitrary community CLI tools remain under development.

## Community and hosted editions

Both editions use the same core authentication and execution engine.
`RIGHAVEN_EDITION=cloud` identifies a hosted deployment, not a completed SaaS
service. Public Cloud onboarding, organization quotas, billing and per-tenant
provider provisioning remain under development.

The former preview's separate users, JWTs, simulated Google/GitHub login,
password reset and custom encrypted vault have been removed.
Authentication uses `/api/v1/auth` and configured native OIDC providers.
No endpoint may reset a password merely from an email address.

## Languages

English is the default. Italian is available in the workspace and shares its
language preference with Gallery and hosting pages. Advanced core surfaces
still fall back to English; some project controls still require localization.
Complete Italian coverage is an open delivery requirement, not a claimed feature.

## Development and verification

Run `python scripts/validate.py` and
`python -m unittest discover -s tests -v` for local checks.
The CI additionally validates real Gateway authentication, Gallery-created native
environments, resource supervision, tools, portable sources and container startup.
Passing isolated unit tests does not certify a public SaaS deployment.

The project is MIT licensed. Incorporated source notices are preserved in
[docs/UPSTREAM-LICENSE](docs/UPSTREAM-LICENSE).
