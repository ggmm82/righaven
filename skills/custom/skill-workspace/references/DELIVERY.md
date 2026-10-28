## Informazioni obbligatorie sui file consegnati

«Creato dallo specialista» non significa «apribile nell’app omonima». Distingui sorgente modificabile, pacchetto sorgenti con dipendenze, export, anteprima e rapporto. Un export può essere modificabile solo in parte o in un’altra app; non promettere struttura, livelli, formule, timeline o parametri che non hai conservato.

- Consegna per impostazione predefinita il sorgente del risultato e gli export richiesti. Riapri il sorgente salvato con l’app di destinazione in una nuova sessione e controlla le parti modificabili. Un’estensione, un header valido, un render o un viewer non è una prova di riapertura nell’app. La prova CLI non certifica automaticamente la GUI o app terze.
- Salva i sorgenti destinati all’utente fuori da `work/` e includili in `output_files`, insieme agli archivi necessari: saranno presentati come download. Conserva distinti gli input originali in `source_files`. Non sostituire il progetto finale con uno script, un log, una ricetta o un sorgente di un passaggio precedente quando serve la struttura modificabile del prodotto finale.
- Per progetti con media collegati crea un pacchetto autosufficiente con struttura e dipendenze reali. Prova estrazione e riapertura da una cartella nuova, evitando percorsi assoluti della sandbox. Includi istruzioni brevi per aprire il progetto; non redistribuire font o risorse senza autorizzazione, ma dichiara le dipendenze non incluse. Un archivio non è esso stesso il formato nativo dell’app: spiega cosa estrarre e aprire.
- `delivery` è obbligatorio nei nuovi job. `source_status` è `included` quando i sorgenti sono scaricabili; `unavailable` se non puoi fornirli, con motivo in `source_note` e `warnings`; `not_applicable` solo per un incarico di sola analisi/rapporto senza prodotto da modificare. Non usare `not_applicable` per nascondere un export privo di sorgente.
- In `delivery.files` descrivi **ogni** file in `output_files` (facoltativamente anche le anteprime): `path`, `role` (`editable_source`, `source_archive`, `export`, `dependency`, `preview`, `report`), `format`, `open_with`, `editability`, `reopen` con `status`/`evidence`, `limitations`. Per `source_archive` indica il progetto interno da aprire dopo estrazione. `included` non significa riapertura verificata: se manca o fallisce la prova, registra `not_run`/`failed`, limiti e avviso; il coordinatore deve trattare la consegna come parziale.
- `open_with` indica l’app e la modalità effettivamente provate, non il nome dello specialista dedotto dal ruolo. `editability` descrive cosa rimane modificabile (e cosa è appiattito). Il runtime controlla file e coerenza dei metadati, non esegue al posto tuo la prova di compatibilità. Non compilare `passed` senza un comando/tool reale e una verifica della struttura.
- Nella risposta finale al coordinatore riporta file, tipi, app di apertura e limiti in termini comprensibili all’utente. La mancanza di un sorgente equivalente è un requisito incompleto da dichiarare, non un motivo per inventare una conversione o rinominare un file.


## Schema di consegna

In `purpose=preview` conserva il sorgente riapribile e le risorse necessarie alla prova. Il pacchetto portabile può essere rinviato: `delivery.finalization_pending` registra ciò che resta obbligatorio per la consegna finale. Non preparare un archivio e una documentazione completi a ogni ritocco, salvo che la prova riguardi proprio la portabilità. Gli archivi effettivamente dichiarati vengono comunque verificati; file mancanti, riaperture fallite e difetti reali restano errori.

Esempio strutturale: sostituisci i percorsi con quelli reali di `RIGHAVEN_OUTPUT_DIR` e riporta esclusivamente prove effettive.

```json
{
  "task": "Descrizione della consegna",
  "source_files": ["/mnt/user-data/uploads/input.xlsx"],
  "output_files": ["/mnt/user-data/outputs/gridcraft/RUN/risultato.xlsx"],
  "previews": [],
  "checks": [
    {"name": "Riapertura export", "status": "passed", "evidence": "Comando reale e risultato osservato"},
    {"name": "Ispezione visiva", "status": "not_run", "evidence": "Visione non disponibile nel motore selezionato"}
  ],
  "warnings": [],
  "delivery": {
    "source_status": "included",
    "source_note": "Workbook con celle e formule modificabili; nessun collegamento esterno.",
    "files": [{
      "path": "/mnt/user-data/outputs/gridcraft/RUN/risultato.xlsx",
      "role": "editable_source",
      "format": "XLSX",
      "open_with": "GridCraft: aprire risultato.xlsx",
      "editability": "Celle, formule e fogli; nessuna immagine sostitutiva del foglio.",
      "reopen": {"status": "passed", "evidence": "ESEMPIO DA SOSTITUIRE: comando di riapertura e formula/valore realmente osservati"},
      "limitations": []
    }]
  }
}
```


## Pacchetti portabili e controlli indipendenti

Il runtime ora costruisce `delivery-manifest.json`: identità della consegna, hash dei file, istruzioni e limiti. Non scriverlo tu. Distingue consegna completa, bozza e sorgenti da correggere; `ok` indica che l’incarico è terminato, non che il prodotto abbia qualità approvata.

Per FilmCraft, EffectCraft e SoundCraft usa il raccoglitore verificato, senza inventare script di confezionamento:

```bash
/usr/bin/python3 /opt/righaven-worker/source_packages.py pack "$RIGHAVEN_OUTPUT_DIR/progetto.fcproj" "$RIGHAVEN_OUTPUT_DIR/Sorgenti.zip"
/usr/bin/python3 /opt/righaven-worker/source_packages.py verify "$RIGHAVEN_OUTPUT_DIR/Sorgenti.zip" --native
```

Adatta l’estensione al progetto reale. Il comando raccoglie riferimenti esatti, riscrive solo i collegamenti, estrae altrove e riapre con la CLI. Se manca una dipendenza, correggi il progetto originale con il percorso reale e ripeti il solo confezionamento. Non cercare file omonimi a caso. Per FilmCraft il pacchetto include `PREPARA_SORGENTI.py`: dopo estrazione l’utente lo esegue con Python 3 e apre il `.locale.fcproj` generato, oppure usa File > Link Media. Spiega questo passaggio in `open_with`; i percorsi relativi della 0.7.2 da soli non garantiscono apertura da altre cartelle. Non promettere GUI o app web non provate.

Per una consegna con più discipline includi i pacchetti completi dei colleghi o le loro cartelle già collaudate. Non copiare un `.ecproj` isolato dimenticando texture o sequenze di frame. Ogni ZIP annidato viene controllato; un sorgente rotto non è giustificato dalla presenza di un altro ZIP valido. Per altri formati restano obbligatorie le verifiche native specifiche della skill: il controllo generico dell’archivio non le sostituisce.


## Capacità, componenti e sincronismo della consegna

### Prova tecnica e prova di realizzazione

Verifica separatamente authoring degli asset, importazione e resa nel prodotto
finale. Una CLI che importa un modello non è necessariamente il metodo migliore
per modellarlo; gli strumenti pertinenti possono collaborare senza sequenze fisse.
Prima di rifinire un asset difettoso, individua la causa osservabile: costruzione,
scala/orientamento, parti e materiali, collegamenti, illuminazione o composizione,
secondo la disciplina. Verifica il requisito nel risultato effettivo, non soltanto
nello script o nel numero di oggetti. Un esempio minimo documenta un’API, non lo
stile o il livello di finitura richiesti.

Il campione riduce estensione o durata, conservando il livello di finitura e la
parte più rischiosa. Confrontalo col migliore precedente sullo stesso requisito.
Una regressione non sostituisce la base valida. Segna in `handoff.checks` i requisiti
effettivamente falliti con `status:failed`, anche se salvataggio e riapertura sono
riusciti. Non limitarti a warning o formule come «campione tecnico»: il runtime
deve poter richiedere la revisione della lavorazione. Distingui nelle lezioni
«come far funzionare la CLI» da «come ottenere un risultato migliore».

Prima di uno script usa-e-getta, consulta `craft capabilities APP` e `references/CAPABILITIES.md` della skill pertinente. La mappa orienta per obiettivo; non certifica ogni comando registrato. Le fixture delle ricette verificano le API, non definiscono una finitura accettabile. Un campione corto deve usare costruzione, dettaglio e resa del prodotto previsto.

Per `purpose=delivery` aggiungi `delivery.components`, da una a dodici componenti raggruppate per lavorazione reale. Ogni elemento ha `name`, `tool` effettivamente usato, `artifacts` e `sources`: liste di riferimenti `{"path":"percorso scaricabile"}` oppure `{"path":"Sorgenti.zip","member":"Audio/sessione.scraft"}`. Usa percorsi assoluti reali negli esempi. Per una sequenza numerosa, un riferimento in `artifacts` può usare `member:"frames/"`: copre tutti i file della cartella realmente presente nello ZIP verificato. Per ZIP annidati usa il percorso logico `member:"SoundCraft/sources.zip/sessione.scraft"`; il runtime risolve soltanto membri realmente presenti negli archivi verificati, senza appiattirli. In `sources` indica sempre il file sorgente effettivo, non una cartella. Copri anche immagini, audio e mesh interni agli ZIP: una timeline video non conserva gli strumenti e le note che hanno creato la musica. I riferimenti devono esistere nei file consegnati o in archivi collaudati. Per SoundCraft occorrono `.scraft` e media; se hai creato una componente via codice dichiara quel metodo e rendi scaricabili ricetta, parametri e input necessari, senza attribuirla a un’app non usata. La ricetta non sostituisce un documento nativo richiesto dall’utente. `provided_inputs` può elencare solo originali caricati dall’utente, identici byte per byte alle componenti riutilizzate. Il controllo è di inventario, non prova di rigenerazione o compatibilità GUI.

Per media sincronizzati usa un riferimento temporale comune: secondi, fps, sample rate, origine, BPM e tick quando pertinenti. Conserva cue, stem, sessioni e collegamenti. Per eventi audiovisivi distinti aggiungi `delivery.timing` con `master` uguale al video scaricabile e `cues:[{"name":"evento osservato","visual_seconds":1.0,"tolerance_seconds":0.12}]`. Sono dati del master effettivo, non tempi dedotti solo dallo script. Il runtime confronta i transienti numerici del master con gli istanti visivi dichiarati: un errore rilevato richiede correzione. Audio continuo o ambiguo rimane `not_run`, da valutare con un metodo pertinente; non inventare cue per superare il controllo. Un picco coincidente non identifica il suono né prova che l’evento visivo sia corretto. La stessa durata di audio e video non dimostra sincronismo e una misura non equivale ad ascolto.

Prima di chiudere valuta anche se è emersa una lezione nuova e trasferibile. Se non emerge, registra `{"lessons":[],"reason":"Motivo concreto"}` in `work/tool-lessons.json`. Il registro non è un download finale. I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. I fatti particolari rimangono nelle prove.


## Preflight nella stessa sandbox

Il preflight controlla anche l’inventario delle componenti e i membri degli ZIP, senza eseguire sorgenti. `components[].name` ammette 1–140 caratteri; `tool` 1–48: usa l’ID breve effettivo (`calibre`, `python3`, `image_gen.imagegen`), non la spiegazione del procedimento. Gli errori indicano il campo e il limite. Correggi i metadati e ripeti il preflight sugli stessi prodotti nella sessione attuale. Il controllo finale esegue comunque le verifiche native: un inventario valido non certifica che i sorgenti si riaprano.

Un vecchio test fallito rimane `failed`. Se una nuova esecuzione pertinente lo ha realmente superato, conserva il vecchio elemento con `scope:"historical"` e `superseded_by:"Nome univoco del nuovo controllo"`; il successore deve essere `scope:"current"` (o omesso), `status:"passed"` e descrivere file/versioni osservati. Il runtime richiede il successore positivo: un’etichetta storica da sola non rimuove un blocco. Non segnare historical un errore ancora attuale, non collegare test diversi e non usare un limite non verificato come successore. Le verifiche native del prodotto corrente restano indipendenti e bloccanti. Conserva la causa e la correzione nelle evidenze; registra una singola lezione generale utile secondo LEARNING.md.

Prima di concludere usa `/usr/bin/python3 /opt/righaven-worker/handoff.py validate "$RIGHAVEN_OUTPUT_DIR"`. Se il manifest è incompleto, correggilo sugli stessi file: il comando restituisce l’errore prima della chiusura del worker. `/usr/bin/python3 /opt/righaven-worker/handoff.py schema` espone lo schema comune anche a Codex e Antigravity, identico a `submit_handoff`. Il preflight non approva il prodotto, non verifica da solo la compatibilità nativa e non riscrive giudizi. Mantieni i controlli falliti e dichiara un limite quando una riapertura resta `not_run` o `failed`.
