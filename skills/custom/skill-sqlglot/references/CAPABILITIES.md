# Capacità operative: sqlglot

Versione esaminata: **30.25.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Parse SQL dialects and derive table/column lineage using real expressions and actual supplied schemas..
**Sorgenti:** Original SQL, actual schema dictionary, normalized SQL, lineage JSON and limits..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Parse and normalize SQL and derive actual table/column lineage where schema is available; do not invent business meaning or execute SQL. | `sqlglot.analyze` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Parsing does not execute SQL or prove database semantics. Unknown columns, wildcard expansion, dynamic SQL and missing schema remain explicit limits; never invent lineage. Use SchemaCrawler/dlt for live metadata and SQLMesh for executable model plans.

## Scoperta mirata

1. `craft capabilities sqlglot`: selezione per obiettivo e confini.
2. `craft commands sqlglot`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools sqlglot --out "$RIGHAVEN_OUTPUT_DIR/work/sqlglot-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `6987964ecdf470692b65ea532d79697dd538c0887b64ab6dd3217007cc798c73`.
Fonte: https://github.com/tobymao/sqlglot. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
