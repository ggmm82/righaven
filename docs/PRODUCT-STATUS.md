# Product architecture and delivery status

RigHaven combines a persistent agent workspace, dynamic project roles and an
on-demand toolbox. Community and hosted deployments use the same execution
engine, account identity and permission boundaries.

## Implemented boundaries

- Core sources are maintained under `core/`, with no remote source checkout.
- User, session and native Agent ownership come from the core authentication layer.
- Gallery activation installs a scanned native skill or creates a native
  environment configuration. Runtime tool dependencies come from managed recipes.
- Published community versions are immutable. Publisher identity is taken from
  the authenticated session, never a submitted author or workspace path.
- Personal workspace language preferences also control Gallery and hosting pages.

## Workspace management

Administrators can create accounts, assign configured roles, suspend/reactivate
access, reset temporary passwords and revoke sessions. Ordinary users can inspect
all visible skill instructions and create scanned personal overrides, including
reference edits. The environment detail view separates observed program versions
from requested choices and links to the skill instructions it uses. The former
Team Profiles surface is the advanced editor of those same native profiles,
not a separate store or a mandatory static team.

Reset operations are owner-scoped, previewed and require an expiring single-use
typed confirmation. Shared model/version resets remain administrator-only.
Accounts, credentials and shared software images are retained.

Claude Code is an optional official CLI provider, prepared on demand rather than
preloaded into every software environment. The data-engineering preset combines
usql, SchemaCrawler, dlt, SQLMesh and SQLGlot with existing notebook/report tools.
See DATA-ENGINEERING.md for connection handling and verification limits.

## Outstanding delivery requirements

- Public directory hosting and publisher-signed distributions. Pinned HTTPS
  catalog synchronization and export are implemented in the Gallery.
- Generic, reviewed onboarding of CLI tools outside the managed runtime catalog.
- Shared organization membership, invitations, commercial plans and token billing.
  The hosted preview has private encrypted API profiles and a transactional ledger
  for account job admission, concurrent jobs and monthly starts. This is not yet
  certification of a public multi-tenant SaaS.
- Complete Italian localization, including project controls and advanced settings.
- Further separation of optional channels, terminal UI and alternative sandbox
  backends. Editorial pages, static demo data and MDX compilation have been removed;
  production images exclude development dependency groups. See CORE-BOUNDARY.md.

The Cloud preview no longer exposes a second account database, simulated OAuth,
unchecked password reset or a custom encrypted key store. Those are not substitutes
for the hosted requirements above. A green Community deployment pipeline is not
certification of a public SaaS or a completed Hub.
