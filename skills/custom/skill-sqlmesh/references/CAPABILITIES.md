# Capacità operative: sqlmesh

Versione esaminata: **0.236.4**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Plan, test and explain SQL/Python analytical transformations using an isolated local DuckDB project..
**Sorgenti:** SQL/Python models, tests, configuration, copied project, DuckDB results and plan/audit evidence..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Validate tests and explain a SQL/Python transformation project in an isolated local DuckDB environment. Apply only with apply_local=true; never auto-apply to a remote database. | `sqlmesh.plan` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Explain the actual graph and reconcile known totals. Apply only when apply_local=true, in the isolated copied project. This adapter does not deploy to remote production. Exchange JSONL/CSV/Parquet rather than assuming all DuckDB file versions interoperate.

## Scoperta mirata

1. `craft capabilities sqlmesh`: selezione per obiettivo e confini.
2. `craft commands sqlmesh`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools sqlmesh --out "$RIGHAVEN_OUTPUT_DIR/work/sqlmesh-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `53ff165e60a70889c985d38ecff3fb7710e55272431a1dfd2b957c4ca5672221`.
Fonte: https://github.com/TobikoData/sqlmesh. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
