# RigHaven core

The application engine and web workspace are maintained in this repository.
Gateway and frontend images build directly from `core/backend` and
`core/frontend`. No external source checkout, package alias, or compatibility
loader is used at build time or runtime.

The backend workspace contains the local `righaven-harness` and
`righaven-extension-api` distributions, imported as `righaven_core` and
`righaven_extension_api`. Configuration uses `RIGHAVEN_*` throughout.

Third-party notices are preserved in `docs/UPSTREAM-LICENSE`. The incorporated
source snapshot was audited at commit
`0bbcccfeb117a73cdeb7a8366f56ba71c25d6f5d`; future changes are reviewed and
tested together with the application in this repository.
