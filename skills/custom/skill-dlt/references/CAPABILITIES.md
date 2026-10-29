# Capacità operative: dlt

Versione esaminata: **1.31.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Discover SQL/document source metadata and extract bounded data into a reproducible local pipeline..
**Sorgenti:** Python pipeline, schema YAML/JSON, query/inputs, portable JSONL, DuckDB snapshot and row reconciliation..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Inspect SQL metadata with SQLAlchemy or MongoDB collection structure. Produce editable schema JSON; sampling is not complete semantic understanding. | `dlt.discover` |
| Extract bounded local JSON/CSV or authorized read-only SQL/MongoDB data into a private DuckDB pipeline. Preserve pipeline, schema, receipt and reconciliation. | `dlt.extract` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Separate SQL metadata, sampled document fields and business hypotheses. Keep pipeline state private per job, preserve type/null semantics and reconcile counts. External reads require authorized read-only credentials; no source-system writes are performed.

## Scoperta mirata

1. `craft capabilities dlt`: selezione per obiettivo e confini.
2. `craft commands dlt`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools dlt --out "$RIGHAVEN_OUTPUT_DIR/work/dlt-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `2d0f7aebfdf4dc85c530e515fcdba4c8fc46399bad6b3ffa851a6469b1e0b337`.
Fonte: https://github.com/dlt-hub/dlt. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
