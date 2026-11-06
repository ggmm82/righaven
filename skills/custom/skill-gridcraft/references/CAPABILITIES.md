# Capacità operative: gridcraft

Versione esaminata: **v0.11.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Fogli di calcolo, formule, tabelle, grafici, analisi e reporting.
**Sorgenti:** XLSX con formule/dati/grafici; export PDF/CSV separati.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Formule e calcolo | `cell.set`, `formulas.insertFunction`, `formulas.autoSum`, `formulas.defineName` |
| Tabelle e dati | `insert.table`, `data.fromTextCsv`, `data.sort`, `data.filter`, `data.removeDuplicates`, `data.validate` |
| Pivot e analisi | `insert.pivotTable`, `pivot.addField`, `pivot.valueSettings`, `pivot.group`, `data.goalSeek`, `data.solver` |
| Grafici | `insert.chart`, `chart.set`, `chart.switchRowColumn`, `insert.sparkline` |
| Stampa, protezione e verifica | `pageLayout.printArea`, `file.exportPdf`, `review.protectSheet`, `document.inspect` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Verificare ricalcolo, unità e formule reali; valori incollati o immagini non sono un modello modificabile. Compatibilità macro/importazioni non universale.

## Scoperta mirata

1. `craft capabilities gridcraft`: selezione per obiettivo e confini.
2. `craft commands gridcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools gridcraft --out "$RIGHAVEN_OUTPUT_DIR/work/gridcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 346 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `e843f5a6a45e65de78fd85fce23e16aba479b767cffb1b50429c363baaf30b4d`.
Fonte: https://github.com/storytold/gridcraft/tree/v0.7.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
