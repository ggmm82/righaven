# Capacità operative: schemacrawler

Versione esaminata: **v17.16.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Reverse engineer real keys, constraints, table relationships and schema metadata through JDBC..
**Sorgenti:** Schema JSON/HTML/DOT, database snapshot or connection requirements, diagrams and interpretation notes..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Reverse engineer actual database schema, keys, constraints and associations with JDBC. Inferred relations remain hypotheses. | `schemacrawler.inspect` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Separate declared constraints from inferred associations and sampled data. Validate business meaning with the owner; do not invent tables or relationships from names. The bundled distribution uses GPL v3 and retains JDBC notices.

## Scoperta mirata

1. `craft capabilities schemacrawler`: selezione per obiettivo e confini.
2. `craft commands schemacrawler`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools schemacrawler --out "$RIGHAVEN_OUTPUT_DIR/work/schemacrawler-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `ca69d25575b37db2c3a46b1ec4e200a7bc7cb46f69785b61ca316f81d84ec4b2`.
Fonte: https://github.com/schemacrawler/SchemaCrawler. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
