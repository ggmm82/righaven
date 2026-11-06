# pdfcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Unione verificata con ordine preservato
```bash
pdfcraft-cli info "$INPUT"
pdfcraft-cli combine "$INPUT" "$APPENDIX" --out "$RIGHAVEN_OUTPUT_DIR/unito.pdf"
pdfcraft-cli info "$RIGHAVEN_OUTPUT_DIR/unito.pdf"
pdfcraft-cli text "$RIGHAVEN_OUTPUT_DIR/unito.pdf"
```
Prova eseguita: due PDF contenenti marcatori diversi → un PDF di due pagine. Il controllo confronta il conteggio `pages` e l’ordine dei marcatori nel testo estratto. Per redazione, firme, OCR o moduli serve una ricetta distinta con strumenti effettivamente presenti nel registro: questa unione non li convalida.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `pdfcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il PDF risultante, riaperto con PdfCraft, precisando quali operazioni restano possibili (pagine, annotazioni, moduli o testo secondo la release e il file). Se il lavoro parte da un documento Word, slide o impaginato creato dalla squadra, includi anche quel sorgente tramite lo specialista che lo ha prodotto. Un PDF è modificabile nei limiti di PdfCraft ma non equivale al progetto editoriale originale: non promettere stili Word, formule, livelli o font che non sono stati conservati. Per PDF scansionati o appiattiti dichiara espressamente i limiti.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
