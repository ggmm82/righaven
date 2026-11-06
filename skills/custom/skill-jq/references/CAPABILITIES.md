# Capacità operative: jq

Versione esaminata: **1.6**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Apply a jq filter to JSON and save the result; the filter is kept with the output.
**Sorgenti:** Input JSON, filter and result.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Apply a jq filter to JSON and save the result; the filter is kept with the output. | `jq.transform` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

A filter that runs is not a validated transformation; compare counts and key values with the source.

## Scoperta mirata

1. `craft capabilities jq`: selezione per obiettivo e confini.
2. `craft commands jq`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools jq --out "$RIGHAVEN_OUTPUT_DIR/work/jq-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `9a5984e8ba09f722c04fb12b1bdbade39c23bdbde7fd2cc563a1883a00131f40`.
Fonte: https://github.com/jqlang/jq. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
