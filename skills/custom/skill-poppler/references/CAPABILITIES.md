# Capacità operative: poppler

Versione esaminata: **22.12.0-2+deb12u2**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Rasterize the final PDF and extract its actual text for independent review.
**Sorgenti:** Original PDF, numbered page PNGs, extracted text and rendering settings.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Rasterize the actual delivered PDF to numbered PNG pages for visual inspection; rendering is not visual approval. | `poppler.render` |
| Extract text from the actual PDF, preserving layout where possible; not OCR or visual validation. | `poppler.text` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Render the exact delivery hash. PNG creation is not a visual judgment; use an available visual model or request user review. Render in bounded batches.

## Scoperta mirata

1. `craft capabilities poppler`: selezione per obiettivo e confini.
2. `craft commands poppler`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools poppler --out "$RIGHAVEN_OUTPUT_DIR/work/poppler-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `6a060bb8b03ee2f002d1e9ed36d5c6cfe0213b01f08bb1730c76303e7d9e0b6e`.
Fonte: https://poppler.freedesktop.org. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
