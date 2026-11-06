# Capacità operative: faker

Versione esaminata: **40.43.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Generate deterministic, foreign-key consistent stub data from the schema model for a batch (periodic runs use increasing batch numbers) into a DuckDB copy and Parquet/CSV/JSON Lines/XML files.
**Sorgenti:** Schema model, generator script, per-batch CSV/Parquet/JSON Lines/XML files, stub DuckDB database and manifest.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Generate deterministic, foreign-key consistent stub data from the schema model for a batch (periodic runs use increasing batch numbers) into a DuckDB copy and Parquet/CSV/JSON Lines/XML files. Data is synthetic; PII columns are always fake. | `faker.generate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Stub data is synthetic: value distributions and correlations do not reproduce production data; updates and deletions are not simulated.

## Scoperta mirata

1. `craft capabilities faker`: selezione per obiettivo e confini.
2. `craft commands faker`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools faker --out "$RIGHAVEN_OUTPUT_DIR/work/faker-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `0240c72357318da083b4ec61dc2c5ee959fb27e9deb6fad8e6f1bcf9d707807f`.
Fonte: https://github.com/joke2k/faker. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
