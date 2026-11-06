# Capacità operative: hledger

Versione esaminata: **1.25**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Check a plain-text journal: parsing, balanced transactions and balance assertions; strict also requires declared accounts and commodities.
**Sorgenti:** Journal file, CSV reports and native check output.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Check a plain-text journal: parsing, balanced transactions and balance assertions; strict also requires declared accounts and commodities. Errors are reported, never corrected. | `hledger.check` |
| Run a native report on a plain-text journal and save CSV; the journal stays the editable source. Totals reflect only the recorded entries. | `hledger.report` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Reports reflect only the recorded entries; a balanced journal is not an audited account or tax advice.

## Scoperta mirata

1. `craft capabilities hledger`: selezione per obiettivo e confini.
2. `craft commands hledger`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools hledger --out "$RIGHAVEN_OUTPUT_DIR/work/hledger-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `a6d6d5979f9b8ca5e2262f8e78ea8d937f10ae3147421a455fb19ba385f715e2`.
Fonte: https://github.com/simonmichael/hledger. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
