# Capacità operative: ocrmypdf

Versione esaminata: **14.0.1+dfsg1-1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Add an OCR text layer and text sidecar to scanned PDFs while preserving the original.
**Sorgenti:** Original scan, searchable PDF, sidecar, language and OCR recipe.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Create a searchable PDF and text sidecar without overwriting the scan. OCR accuracy requires content review. | `ocrmypdf.ocr` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Do not replace original scans. Check names, numbers, reading order and language against sampled images; OCR confidence is not accuracy. This adapter does not claim PDF/A.

## Scoperta mirata

1. `craft capabilities ocrmypdf`: selezione per obiettivo e confini.
2. `craft commands ocrmypdf`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools ocrmypdf --out "$RIGHAVEN_OUTPUT_DIR/work/ocrmypdf-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `8f936f19e5fc83ac31a5317df72bd3eba9bfadc1c242eb5c25a10a9cadd9491c`.
Fonte: https://github.com/ocrmypdf/OCRmyPDF. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
