# Capacità operative: pdfcraft

Versione esaminata: **v0.13.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Ispezione e modifica PDF, pagine, testo, moduli, OCR e prestampa.
**Sorgenti:** PDF modificato e originali/ricetta; progetto editoriale da conservare separatamente.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Pagine e oggetti | `page_render`, `object_list`, `object_move`, `page_rotate`, `page_enhance_camera` |
| Testo e ricerca | `text_extract`, `text_find`, `text_lines`, `text_font_files`, `text_font_import` |
| Moduli e annotazioni | `form_fields`, `form_fill`, `form_reset`, `form_add_field`, `form_set_image` |
| OCR, conversione e ottimizzazione | `doc_batch`, `ocr_recognize`, `ocr_recognize_files`, `ocr_status` |
| Controlli, accessibilità e stampa | `doc_info`, `printers`, `printer_options`, `accessibility_autotag_preview`, `accessibility_autotag_apply` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

OCR usa modelli installati. PDF strutturalmente valido o taggato non certifica qualità narrativa/visiva. Non ricostruisce automaticamente il progetto di impaginazione.

## Scoperta mirata

1. `craft capabilities pdfcraft`: selezione per obiettivo e confini.
2. `craft commands pdfcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools pdfcraft --out "$RIGHAVEN_OUTPUT_DIR/work/pdfcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 175 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `fde4a9de19f21da50f9229d287ef635d504cc04bf30c92b5be8f045fed273336`.
Fonte: https://github.com/storytold/pdfcraft/tree/v0.8.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
