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
