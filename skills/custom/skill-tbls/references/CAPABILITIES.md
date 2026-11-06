# Capacità operative: tbls

Versione esaminata: **v1.96.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Generate the data catalog from the schema model: Markdown pages per table, ER diagram, relations, labels and description coverage.
**Sorgenti:** Schema model JSON, generated tbls schema, configuration, Markdown pages and ER diagram.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Generate the data catalog from the schema model: Markdown pages per table, ER diagram, relations, labels and description coverage. | `tbls.document` |
| Check the schema model against catalog rules (table and column descriptions, primary keys, unrelated tables, column count) and save the findings. | `tbls.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

The catalog documents the model it is given; descriptions, owners and business meaning must be confirmed by people who know the data.

## Scoperta mirata

1. `craft capabilities tbls`: selezione per obiettivo e confini.
2. `craft commands tbls`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools tbls --out "$RIGHAVEN_OUTPUT_DIR/work/tbls-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `9decfdc4662808f2243c12192c6d05e5c43c8d234ada03c89543c1f351a9d90a`.
Fonte: https://github.com/k1LoW/tbls. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
