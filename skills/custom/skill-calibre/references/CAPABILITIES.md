# Capacità operative: calibre

Versione esaminata: **9.17.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Produzione e conversione editoriale, EPUB/AZW3, metadati, risorse e librerie.
**Sorgenti:** XHTML/CSS/OPF e risorse, ebook ricostruibile e input editoriali.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Conversione e composizione | `calibre.convert` |
| Metadati e finitura | `calibre.metadata`, `calibre.polish` |
| Sorgenti ricostruibili | `calibre.unpack`, `calibre.pack` |
| Riapertura e controlli | `calibre.inspect`, `calibre.check` |
| Libreria locale | `calibre.library` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

L’adattatore non esaurisce ebook-convert, ebook-meta, ebook-polish, calibre-debug e calibredb. Non scrive automaticamente un buon libro né garantisce identica resa su tutti i lettori. Rendering headless tramite Xvfb; verifica struttura e risorse distinta dalla revisione editoriale.

## Scoperta mirata

1. `craft capabilities calibre`: selezione per obiettivo e confini.
2. `craft commands calibre`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools calibre --out "$RIGHAVEN_OUTPUT_DIR/work/calibre-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 8 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `32fa21ebc9d7245671a7475b582d90847d530faffecdbea7b81042aba0da9065`.
Fonte: https://github.com/kovidgoyal/calibre. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
