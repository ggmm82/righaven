# Regia adattabile

Compila i ruoli professionali dal brief con `harness_plan(roles_json=...)`, senza un elenco di professioni. Il catalogo contiene gli strumenti installati, non tutti i mestieri possibili: seleziona le CLI pertinenti oppure usa il workspace senza CLI. Esegui i ruoli compilati con `harness_delegate(agent="workspace", role_id=...)` e torna ai ruoli quando il prodotto lo richiede. La memoria delle attività non è una pipeline rigida: si può cambiare ordine, aggiungere un’integrazione di prova prima della produzione completa e far controllare a un collega i risultati incompleti.

## Capacità, prove e collaborazione

La squadra nasce dai requisiti, non da una sequenza di app per settore. Individua la decisione o la capacità più incerta e fai produrre un campione rappresentativo prima di moltiplicare la lavorazione. Può essere un modello, una pagina, una funzione eseguibile, un calcolo o qualunque altro output pertinente: non sono tipi di progetto predefiniti.

Verifica prima le operazioni native; considera composizione fra strumenti, authoring e programmazione quando adatti. L’assenza di un comando automatico non esclude tutte le alternative; una prova tecnicamente valida non dimostra da sola il livello qualitativo richiesto. Registra metodo provato, file, controlli falliti e limiti osservati nella memoria del progetto.

Assegna competenze concrete, input e verifiche ai ruoli dinamici. Ogni collaboratore deve ricevere le CLI necessarie alla propria verifica, anche se non produce il file originale. Il revisore osserva il risultato esatto, identifica difetti e confronta la correzione con la versione precedente. Un programma in più non equivale automaticamente a un risultato migliore.

Mantieni `summary` e `next_action` brevi. Il pannello Progetto mostra risultato e lavoro della squadra attuale; le attività degli altri contesti restano espandibili. I file e le versioni rimangono disponibili senza imporre una sequenza rigida.

## Recupero

- Un WAV già esportato può essere verificato e importato in FilmCraft anche se SoundCraft ha esaurito i turni prima del manifesto.
- Una revisione dell’animazione non cancella il mix pronto. Controlla se tempi e cue cambiano; aggiorna solo le parti coinvolte.
- Una quota esaurita richiede pausa e azione sul servizio condiviso. Conserva i file e mostra il problema in chiaro; non continuare a chiamare lo stesso provider.
- Un controllo GUI non disponibile va dichiarato, non aggirato inventando un passed e non usato come motivo per ricominciare tutto.
- Un risultato utile ma provvisorio può diventare input di una verifica. Per la consegna finale restano necessari sorgenti, risorse, riapertura e requisiti reali del prodotto.

## Accettazione della consegna

`purpose=delivery` prepara una versione disponibile; leggi `delivery.issues` e completa i sorgenti prima di dichiararla pronta. `purpose=review` valuta separatamente il file esatto con `quality-review.json` e criteri specifici al brief; il runtime conserva il suo hash. Le verifiche automatiche non sono una recensione artistica. Per audiovisivi la revisione deve includere la modalità realmente necessaria (visione/ascolto), oppure restare da valutare. Il trasporto DeepSeek corrente è solo testuale. Non rigenerare un prodotto perché manca una capacità sensoriale e non cambiare servizio automaticamente.

## Dalla prova al risultato

Definisci la domanda della prova e i `requirement_ids` che deve verificare. Chiedi al revisore un rapporto con `scope` di tipo `checkpoint` (protocollo REVIEW): il verdetto finale rimane completo, quello della prova indica se il metodo risolve il rischio selezionato. Segui `continuation`: correggi i difetti osservati nella prova, oppure passa al prodotto completo riusando il sorgente. Non ripetere prove equivalenti per requisiti deliberatamente rinviati alla consegna.

In `purpose=preview` conserva sorgenti e risorse realmente usate; prepara il pacchetto portabile finale dopo la scelta del metodo, salvo che il rischio da provare sia proprio la portabilità. Gli archivi consegnati vengono comunque collaudati. Prima di `purpose=delivery` risolvi `delivery.finalization_pending` e completa tutti i requisiti della richiesta.

Separa i requisiti per proprietà osservabile: un vincolo misurabile e un giudizio percettivo richiedono controlli distinti. La mancata disponibilità di ascolto/visione non è un difetto del file: dopo i controlli disponibili presenta la versione come da valutare e chiedi la verifica all’utente, senza una rigenerazione automatica. Una dipendenza indispensabile alla produzione va invece dichiarata prima di proseguire.
