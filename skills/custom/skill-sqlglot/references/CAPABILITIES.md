# Capacità operative: sqlglot

Versione esaminata: **30.25.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Parse SQL dialects and derive table/column lineage using real expressions and actual supplied schemas..
**Sorgenti:** Original SQL, actual schema dictionary, normalized SQL, lineage JSON and limits..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Parse and normalize SQL and derive actual table/column lineage where schema is available; do not invent business meaning or execute SQL. | `sqlglot.analyze` |
| Build the engine-neutral schema model (tables, portable types, keys, descriptions, PII, stub hints) from dlt discover metadata, DDL in any dialect or a documented model, then apply documentation overrides. Observed structure is never silently changed. | `sqlglot.model` |
| Generate ordered, re-parsed DDL for a target engine from the schema model; constraints the engine cannot enforce are reported, not hidden. | `sqlglot.ddl` |
| Generate the production package from the schema model: dlt ingestion with incremental cursors, SQLMesh staging views with key audits and an example mart, local and production gateways (PostgreSQL, SQL Server, Fabric or DuckDB), periodic stub job, supercronic crontab, locked job runner, Dockerfile, compose, CI and runbook. No secret values are written. | `sqlglot.scaffold` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Parsing does not execute SQL or prove database semantics. Unknown columns, wildcard expansion, dynamic SQL and missing schema remain explicit limits; never invent lineage. Use SchemaCrawler/dlt for live metadata and SQLMesh for executable model plans.

## Scoperta mirata

1. `craft capabilities sqlglot`: selezione per obiettivo e confini.
2. `craft commands sqlglot`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools sqlglot --out "$RIGHAVEN_OUTPUT_DIR/work/sqlglot-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 4 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `a5cc271bbc0bb7cb6c44474fcb641bd9683a6bd725871d53a9524f2ceea7b23d`.
Fonte: https://github.com/tobymao/sqlglot. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
