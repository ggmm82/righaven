# Capacità operative: duckdb

Versione esaminata: **v2.0.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Query CSV, JSON and Parquet with SQL and a local analytical database.
**Sorgenti:** SQL, input datasets/schema, DuckDB database and result CSV.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Execute a saved SQL recipe on a private database copy; retain SQL and data, return CSV results. | `duckdb.query` |
| Create an empty local DuckDB replica from DuckDB DDL and verify tables, columns and keys against the schema model. | `duckdb.replicate` |
| Infer a schema model from JSON, JSON Lines, Parquet, CSV or XML files (a file or a folder of files); XML records become JSON Lines first. | `duckdb.infer` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Keep NULL handling, types, units and join cardinalities explicit. Disable unneeded extensions; a query result does not prove the underlying data is correct.

## Scoperta mirata

1. `craft capabilities duckdb`: selezione per obiettivo e confini.
2. `craft commands duckdb`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools duckdb --out "$RIGHAVEN_OUTPUT_DIR/work/duckdb-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 3 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `449a5bfed16cb19816052de142e9b9c724e949da7e3d0edf8531c8b207ca5cd2`.
Fonte: https://github.com/duckdb/duckdb. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
