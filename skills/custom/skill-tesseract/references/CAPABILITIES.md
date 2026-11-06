# Capacità operative: tesseract

Versione esaminata: **5.3.0-2**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Recognize text in local images with coordinates and confidence evidence.
**Sorgenti:** Original image, TXT, TSV, language and preprocessing recipe.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Recognize a local image into text and TSV with confidence/coordinates; preserve the original image. | `tesseract.recognize` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Use OCRmyPDF for whole scanned PDFs. Keep low-confidence words visible; confidence is not a guarantee. English and Italian language data are installed explicitly.

## Scoperta mirata

1. `craft capabilities tesseract`: selezione per obiettivo e confini.
2. `craft commands tesseract`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools tesseract --out "$RIGHAVEN_OUTPUT_DIR/work/tesseract-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `c9c345353244ca2482f6683894c890b264677f6d63e6fa8d6e633ef5671396c3`.
Fonte: https://github.com/tesseract-ocr/tesseract. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
