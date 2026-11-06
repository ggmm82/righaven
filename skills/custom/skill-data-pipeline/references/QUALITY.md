# Acceptance of the guided data project

- **Goal and provenance:** preserve the actual user outcome. Distinguish documented, observed and inferred schema facts. Resolve or explicitly accept gaps and uncertain relations.
- **Catalog:** cover source tables and relevant columns, business descriptions, PII labels and a readable relationship diagram.
- **Laboratory:** verify the empty schema and constraints. Distinguish DuckDB simulation from a source-engine replica; never claim engine parity from DDL re-parsing alone.
- **Synthetic scenarios:** verify reproducibility, keys, CHECKs, orphan prevention, updates, deletes and anomalies meaningful to the business.
- **Recurring pipeline:** test a second load without duplicates, transformation audits, reconciliation and recovery after restart. Confirm cursor semantics; a suggestive column name is not sufficient.
- **Business reporting:** deliver actual consultable reports and editable definitions using user-confirmed dimensions and measures. Reconcile KPIs with the source. An example count mart or BI-ready tables do not satisfy this gate.
- **Package:** inspect a successful host-owned harness_package_check report tied to the current package files, not just a generic CI fixture. Check included locks, exact startup instructions, durable state, independent schedules and absence of secrets.
- **User control:** bind phases to native activities, present saved evidence and wait for owner approval. A changed source invalidates dependent approvals without deleting earlier files.

Do not claim external connectivity, permissions, performance, native BI deployment or production verification unless actually tested with authorized access. The synthetic local path remains usable without those connections.
