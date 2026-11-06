# photocraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Conversione conservativa con sorgente modificabile
```bash
photocraft-cli convert "$INPUT" "$RIGHAVEN_OUTPUT_DIR/progetto.pcraft"
photocraft-cli info "$RIGHAVEN_OUTPUT_DIR/progetto.pcraft"
photocraft-cli convert "$RIGHAVEN_OUTPUT_DIR/progetto.pcraft" "$RIGHAVEN_OUTPUT_DIR/finale.png"
```
Prova eseguita: PNG RGBA 64×48 → PCraft → PNG. Dopo riapertura, dimensioni e alpha risultano conservati; il checksum dell’originale resta uguale. Per il lavoro reale confronta anche livelli, modalità e dimensioni con il brief: questa ricetta non prova ogni filtro o tutte le funzioni PSD.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `photocraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il progetto `.pcraft` e gli export richiesti (per esempio PNG/JPEG); PSD è una consegna distinta da verificare se richiesta. Riapri il progetto con PhotoCraft e controlla livelli, maschere, visibilità, dimensioni e risorse. Dichiara quali elementi sono separatamente modificabili: un’immagine appiattita inserita in un progetto o in PSD non recupera livelli, parti del soggetto o effetti procedurali. Non presentare il PNG come sorgente a livelli.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
