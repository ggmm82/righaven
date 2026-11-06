# Capacità operative: miller

Versione esaminata: **6.6.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Convert or transform CSV, TSV or JSON with Miller; an optional DSL script file is kept with the output.
**Sorgenti:** Input data, DSL script and converted result.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Convert or transform CSV, TSV or JSON with Miller; an optional DSL script file is kept with the output. | `miller.transform` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Type inference may change number formats; check separators, encodings and totals against the source.

## Scoperta mirata

1. `craft capabilities miller`: selezione per obiettivo e confini.
2. `craft commands miller`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools miller --out "$RIGHAVEN_OUTPUT_DIR/work/miller-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `48b08a88ea455460e9b9189dbdad0ef92a06befbce5886462d525f3b53ee2bc9`.
Fonte: https://github.com/johnkerl/miller. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
