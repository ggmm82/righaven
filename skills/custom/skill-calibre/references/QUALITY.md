# Controlli della capacità Calibre

- Confronta il risultato con requisiti, uso e riferimenti del progetto: testo integrale, ordine, metadati, titoli, indice, tabelle, immagini e glifi; controlla che conversione o polish non perdano contenuti.
- EPUB/AZW3: `inspect` e `check` reali, nessun errore strutturale; riporta avvisi con motivazione. I criteri non verificabili restano `not_run`.
- Prova i sorgenti dopo trasferimento e ricostruzione; verifica almeno una modifica effettiva e conserva l’originale. Non dichiarare la GUI provata se hai usato solo CLI.
- Confronta resa e leggibilità con i criteri del progetto. Se non puoi aprire il lettore o vedere le pagine, dichiara il limite; non dedurre qualità visiva da un exit code.
- PDF: conta pagine, verifica testo e font, controlla visivamente pagine rappresentative quando disponibile. Non promettere PDF/X o stampa professionale senza controlli specifici.
- DOCX e altri formati: verifica con lo strumento che li aprirà davvero; il checker EPUB non copre quei formati.
- Font e risorse devono essere trasferibili e autorizzati. Nessun riferimento al filesystem del server o a una libreria locale necessaria per aprire il file.
- Prodotto e sorgenti appartengono alla stessa delivery; registra nomi, formato, app/versione, editabilità, comandi di riapertura, evidenze e limiti.
