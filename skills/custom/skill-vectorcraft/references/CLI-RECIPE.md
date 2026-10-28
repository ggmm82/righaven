# vectorcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Creazione da zero e importazione SVG

Per un disegno originale senza input, scrivi prima un SVG XML valido in `$RIGHAVEN_OUTPUT_DIR/work/bozza.svg` con `width`, `height` e `viewBox` coerenti. Definisci davvero il soggetto richiesto con forme/tracciati/gruppi e gradienti standard. Poi imposta `INPUT` a quel file e usa la sequenza seguente: la CLI produce il sorgente editabile e gli export. Non limitarti a preparare un batch di costruzione: esegui la produzione prima di consegnare. Non copiare la fixture del test come prodotto dell’utente.

## SVG con testo modificabile e anteprima
```bash
vectorcraft-cli convert "$INPUT" "$RIGHAVEN_OUTPUT_DIR/logo.vectorcraft"
vectorcraft-cli info "$RIGHAVEN_OUTPUT_DIR/logo.vectorcraft"
vectorcraft-cli convert "$RIGHAVEN_OUTPUT_DIR/logo.vectorcraft" "$RIGHAVEN_OUTPUT_DIR/logo.svg"
vectorcraft-cli convert "$RIGHAVEN_OUTPUT_DIR/logo.vectorcraft" "$RIGHAVEN_OUTPUT_DIR/anteprima.png"
```
Prova eseguita: SVG 160×90 con rettangolo e testo → sorgente VectorCraft → SVG/PNG. Il test indipendente legge XML, verifica `viewBox` e testo SVG editabile e decodifica il PNG. Non usare `--outline-text` quando il testo deve restare modificabile.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `vectorcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il progetto `.vectorcraft` insieme a SVG/PDF/PNG richiesti. Riapri il progetto e verifica oggetti, gruppi, tracciati e testo; per SVG controlla che il testo da modificare non sia stato convertito in contorni e che non sia una sola bitmap incorporata. Distingui sorgente nativo e formato di scambio; segnala font, immagini collegate e caratteristiche non conservate.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
