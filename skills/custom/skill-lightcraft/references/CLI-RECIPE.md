# lightcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Sviluppo RAW senza modificare l’originale
```bash
lightcraft-cli render "$INPUT" -o "$RIGHAVEN_OUTPUT_DIR/sviluppata.png" --set light.exposure=0.5 --size 64
```
Prova eseguita sia su PNG sia su un vero DNG sintetico generato da `lightcraft-cli synth-merge hdr -o CARTELLA_TEST`. Il DNG è stato sviluppato dalla CLI e il suo checksum è rimasto invariato. `--size` indica il lato lungo; 64 è la dimensione della prova, da sostituire con quella di consegna. `--set` imposta uno specifico controllo reale; consulta `lightcraft-cli controls --json` per gli altri. Conserva la ricetta effettiva e verifica campioni e clipping prima di elaborare la serie; la prova non misura la qualità percettiva dei RAW dell’utente.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `lightcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna gli export e i materiali per riprendere lo sviluppo: copie degli originali necessari, ricetta eseguibile con i parametri realmente usati e sidecar/catalogo soltanto se la release ne supporta salvataggio e riapertura. Se usi un pacchetto originali+ricetta, dichiaralo come sorgente riproducibile: non è un progetto nativo apribile con un doppio clic. Riesegui la ricetta su una copia e confronta le impostazioni e l’output. Non chiamare un JPEG/PNG esportato «RAW modificabile», non inventare formati progetto e non modificare gli originali.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
