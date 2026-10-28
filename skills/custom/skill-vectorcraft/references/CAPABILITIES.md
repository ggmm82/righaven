# Capacità operative: vectorcraft

Versione esaminata: **v0.16.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Illustrazione vettoriale, loghi, icone, lettering e diagrammi modificabili.
**Sorgenti:** .vectorcraft/SVG con tracciati e testo; PDF come export.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Forme, oggetti e tavole | `artboard.new`, `artboard.setProps`, `object.transform`, `object.move`, `object.scale` |
| Tracciati e operazioni geometriche | `path.create`, `path.appendAnchor`, `path.close`, `path.setHandle` |
| Tipografia | `text.create`, `text.setText`, `text.areaOptions`, `text.reshapeArea` |
| Aspetto, pennelli e gradienti | `appearance.addFill`, `appearance.addStroke`, `appearance.addEffect`, `paint.setGradientGeom`, `brush.freehand`, `brush.new` |
| Simboli e ripetizioni | `symbol.new`, `symbol.place`, `object.repeat.grid`, `object.repeat.radial`, `object.pattern.make` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Un raster incorporato in SVG rimane raster. Non sostituisce modellazione solida o animazione completa.

## Scoperta mirata

1. `craft capabilities vectorcraft`: selezione per obiettivo e confini.
2. `craft commands vectorcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools vectorcraft --out "$RIGHAVEN_OUTPUT_DIR/work/vectorcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 802 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `0966fb325932d3c80d5c4b576f0a0e554d03feefc7cfd2ca453b92dbf98fc956`.
Fonte: https://github.com/storytold/vectorcraft/tree/v0.11.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
