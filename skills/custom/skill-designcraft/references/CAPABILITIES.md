# Capacità operative: designcraft

Versione esaminata: **v0.12.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Impaginazione multipagina, libri, riviste, fumetti e prestampa.
**Sorgenti:** .designcraft, font/immagini pertinenti e PDF di lettura/stampa.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Pagine, gabbie e impaginazione | `file.new`, `layout.pages.insert`, `layout.pages.applyParent`, `frame.grid`, `layout.createAlternate` |
| Testi, cornici e stili | `frame.create`, `text.insert`, `style.paragraph.create`, `style.paragraph.apply`, `style.character.apply` |
| Immagini e oggetti | `file.place`, `place.load`, `place.drop`, `object.arrange` |
| Tabelle, dati e libri | `book.new`, `book.add`, `table.insert`, `table.setCell`, `data.source.select`, `data.merge` |
| Prestampa e confezione | `preflight.run`, `file.package`, `file.exportPdf`, `file.exportEpub`, `file.exportIdml` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Impagina asset e lettering. Una tavola generata come immagine non contiene vignette o personaggi su livelli separati; descrivere la modificabilità reale.

## Scoperta mirata

1. `craft capabilities designcraft`: selezione per obiettivo e confini.
2. `craft commands designcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools designcraft --out "$RIGHAVEN_OUTPUT_DIR/work/designcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 527 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `b70ddcd51334e99068209888aad4fd0dda6c5dc9dff75095c393378c6641f748`.
Fonte: https://github.com/storytold/designcraft/tree/v0.8.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
