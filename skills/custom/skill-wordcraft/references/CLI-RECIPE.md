# wordcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Relazione strutturata, DOCX e PDF
```bash
wordcraft-cli convert "$RIGHAVEN_OUTPUT_DIR/work/relazione.md" "$RIGHAVEN_OUTPUT_DIR/relazione.docx"
wordcraft-cli inspect "$RIGHAVEN_OUTPUT_DIR/relazione.docx"
wordcraft-cli convert "$RIGHAVEN_OUTPUT_DIR/relazione.docx" "$RIGHAVEN_OUTPUT_DIR/relazione.pdf"
pdfcraft-cli text "$RIGHAVEN_OUTPUT_DIR/relazione.pdf"
```
Prova eseguita: Markdown con titolo e tabella → DOCX con testo e tabella XML veri → PDF con lo stesso marcatore e il totale 60. La ricetta serve per documenti nuovi semplici; per modificare documenti esistenti conserva stili e parti richiesti usando i tool pertinenti. La presenza del testo nel PDF non prova l’impaginazione: resta distinta l’ispezione visiva.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `wordcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il DOCX modificabile con paragrafi, stili e tabelle reali, insieme al PDF richiesto. Riapri il DOCX in WordCraft e verifica la struttura; se redatto da Markdown conserva anche quel sorgente nel pacchetto quando utile, fuori da `work/`. Il PDF non sostituisce il DOCX e un’immagine a pagina intera non è testo modificabile. Dichiara font, campi o parti non conservate; misura il formato pagina effettivo (595×842 pt circa è A4, 612×792 pt è Letter), senza etichette «A4-like».
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
