# Capacità operative: wordcraft

Versione esaminata: **v0.10.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Scrittura strutturata, documenti lunghi, revisioni e apparati editoriali.
**Sorgenti:** DOCX/progetto supportato con struttura, stili e revisioni.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Struttura e stili | `para.heading1`, `para.style`, `styles.create`, `styles.apply`, `styles.inspect` |
| Tabelle e impaginazione | `layout.margins`, `layout.columns`, `table.insertAt`, `table.style`, `text.insert` |
| Revisione e commenti | `review.trackChanges`, `review.newComment`, `review.reply`, `review.resolveComment` |
| Riferimenti e citazioni | `references.toc`, `references.updateToc`, `references.footnote`, `references.citation`, `references.citationStyle` |
| Equazioni e distribuzione | `equation.insertStructure`, `equation.insertSymbol`, `file.exportPdf`, `file.exportPng` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Funzioni Zotero richiedono Zotero attivo; non presumere servizi presenti. Per prestampa complessa può servire DesignCraft; EPUB/device conversion passa a Calibre.

## Scoperta mirata

1. `craft capabilities wordcraft`: selezione per obiettivo e confini.
2. `craft commands wordcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools wordcraft --out "$RIGHAVEN_OUTPUT_DIR/work/wordcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 638 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `531061f857bd4d90ac6f80d79bebc4a0468ddeea527cc69365fee1dfa87f3d2b`.
Fonte: https://github.com/storytold/wordcraft/tree/v0.7.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
