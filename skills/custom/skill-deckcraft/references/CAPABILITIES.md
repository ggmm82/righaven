# Capacità operative: deckcraft

Versione esaminata: **v0.10.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Presentazioni editabili, sistemi di slide, diagrammi, media e animazioni.
**Sorgenti:** .deckcraft e PPTX, con media e limiti di interoperabilità.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Slide, temi e layout | `slide.new`, `slide.duplicate`, `slide.move` |
| Forme e diagrammi | `shape.insert`, `shape.connect`, `shape.freeform`, `insert.smartArt` |
| Testi e tabelle | `text.insert`, `insert.table`, `table.merge`, `table.style` |
| Media e animazioni | `insert.audio`, `insert.video`, `animation.add`, `animation.set`, `media.options` |
| Export e anteprime | `file.save`, `file.export`, `file.render` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Un deck di immagini non equivale a slide con elementi editabili. Verificare separatamente PPTX e animazioni dopo esportazione.

## Scoperta mirata

1. `craft capabilities deckcraft`: selezione per obiettivo e confini.
2. `craft commands deckcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools deckcraft --out "$RIGHAVEN_OUTPUT_DIR/work/deckcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 321 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `ac03611972bb15ea4d41c7606b413b7ca88ede85698aff0c4a86c9e41a9a0ca6`.
Fonte: https://github.com/storytold/deckcraft/tree/v0.7.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
