## Revisione della qualità senza riscrivere il prodotto

Quando `Scopo incarico: review` riguarda il prodotto conclusivo, valuta il file esistente rispetto al brief e ai criteri `references/QUALITY.md`. Usa immagini reali in un tool visivo, campioni delle transizioni e ascolto effettivo quando disponibili. Il collegamento DeepSeek corrente è testuale: non può attestare visione o ascolto. Non modificare il prodotto durante questa verifica; indica difetti e correzioni mirate. Non promuovere una bozza solo perché è decodificabile.

Consegna nella tua cartella `quality-review.json`, ruolo `report`, elencato in `output_files`; il prodotto esaminato deve essere in `source_files`. Se manca `handoff.json` o sono errati i suoi metadati, il runtime compila l’involucro dal rapporto valido, conserva l’originale in work/ e mantiene i controlli dichiarati falliti, senza alterare i giudizi. Il rapporto può indicare `source_files` e deve usare il `product_sha256` effettivamente osservato quando lo dichiara. La revisione non deve copiare o riesportare il prodotto per diventare una consegna valida. Esempio di struttura (non di valutazione da copiare):

```json
{
  "product_path": "/mnt/user-data/outputs/filmcraft/JOB/video.mp4",
  "criteria": [
    {"criterion": "Silhouette e articolazioni leggibili nel brief", "method": "visual", "status": "not_run", "evidence": "Sostituire con osservazioni sui frame reali e tool usato, oppure motivo della mancata visione"},
    {"criterion": "Coreografia e ritmo coerenti con la musica", "method": "listening", "status": "not_run", "evidence": "Sostituire con ascolto e confronto reali, oppure limite della modalità disponibile"}
  ]
}
```

Metodi: `visual`, `listening`, `technical`, `content`. Criteri pertinenti e specifici al prodotto, non una lista generica di complimenti. Stati: `passed`, `failed`, `not_run`. Il runtime lega la valutazione all’hash del prodotto: una modifica richiede revisione della nuova versione. Un prodotto visivo richiede almeno un criterio visivo, un prodotto audio almeno un criterio d’ascolto. Se non puoi valutare, consegna il rapporto e mantieni lo stato da valutare; non avviare rigenerazioni inutili. Non usare sole misure tecniche per approvare contenuto creativo.



## Contratto comune: contenuto richiesto, evidenze e riferimenti

Il runtime fornisce `acceptance` nell’incarico: messaggi originali dell’utente, modifiche successive e requisiti con ID. Il piano del coordinatore è una proposta operativa e non può cambiare da solo il contenuto richiesto. Rispetta i messaggi successivi dell’utente quando correggono i precedenti. Questa procedura è comune a tutti gli strumenti.

Prima di produrre in grande, scegli un campione rappresentativo e verifica il requisito più rischioso con gli input effettivi. Un file valido, dati presenti o segnale non silenzioso non dimostrano che contenuti, calcoli, forma, stile o riferimenti siano quelli richiesti. Se manca un riferimento indispensabile o una capacità reale, segnalalo e conserva i risultati; non sostituire il requisito con un’alternativa più facile senza l’utente.

Nella revisione `quality-review.json` ogni criterio del contratto indica `requirement_id` copiato da acceptance, `criterion`, `method`, `status`, `evidence`. Includi sempre `request_fidelity`: confronta il prodotto con la richiesta originale e le sue modifiche, non con il riassunto del produttore. I criteri non coperti restano non verificati. La revisione è legata sia ai byte del prodotto sia al contratto: una richiesta cambiata non eredita l’approvazione precedente.

I controlli aggiuntivi fuori dal contratto usano `scope:"supplementary"` e **omettono requirement_id**. Restano nel rapporto con l’esito reale e i limiti, senza bloccare un requisito già verificato. Se il contratto richiede collegamenti funzionanti e compatibilità dichiarata, prova i collegamenti; la mancata prova su dispositivi o lettori non richiesti è un limite supplementare. Se invece il requisito richiede quel lettore, dispositivo, accessibilità o certificazione, mantieni il suo ID e `not_run` o `failed`: non riclassificarlo per approvare il prodotto. Il runtime rifiuta un criterio supplementary con requirement_id e controlla comunque tutti i requisiti obbligatori. `critical:false` non rende facoltativo un ID obbligatorio. Non duplicare i controlli supplementari come errori tecnici bloccanti nell’handoff.

Esempio di voce (da adattare e osservare realmente):

```json
{"requirement_id":"request_fidelity","criterion":"Contenuto conforme ai messaggi dell’utente","method":"content","status":"not_run","evidence":"Sostituire con osservazioni reali sul contenuto o con il motivo della mancata verifica"}
```

Metodi comuni: `content` per significato/contenuto, `structural` per struttura modificabile, `functional` per comportamento/calcoli, `reference` per confronto con risorse effettive, `visual` per immagini osservate, `listening` per ascolto effettivo, `technical` per formato/decodifica. Usa il metodo previsto dal requisito, senza rinominare una misura tecnica come giudizio percettivo. Per `reference` devi avere letto i `reference_paths` in `source_files`; il runtime ne conserva gli hash. Se il collegamento non offre il metodo necessario, registra `not_run`. L’ascolto non è attualmente collegato nei trasporti supportati; DeepSeek non offre neppure visione. Un confronto numerico appropriato al requisito può essere descritto come tale, non come ascolto o visione inventati.

Le revisioni possono riusare lo stesso step_id della produzione: il software mantiene il prodotto selezionato, i sorgenti e le revisioni recenti come consegne distinte. Non rigenerare un risultato perché il suo rapporto è diventato il file più recente. Comunica “versione disponibile / requisiti da verificare” finché il contratto non è soddisfatto, senza dichiarare tutto concluso.


## Dalla revisione alla correzione

Le assunzioni del coordinatore non diventano automaticamente vincoli dell'utente. Prima di dichiarare un metodo incapace, confronta le richieste originali e le scelte delegate alla squadra. Descrivi cosa hai realmente provato, quale capacità manca e un'alternativa operativa pertinente. Un ritocco degli stessi elementi non dimostra che sia stato tentato un metodo differente; un titolo professionale non è una prova di competenza. Nella revisione giudica le evidenze indipendentemente dal giudizio suggerito nell'incarico. Non abbassare i criteri per autorizzare la produzione.

Una revisione non termina con una lista di difetti. In `quality-review.json` aggiungi `revision_actions`: fino a 12 oggetti con `requirement_id` del criterio, `action` concreta, `reason`, `priority` 1–3 e `strategy` tra `revise`, `change_method`, `verify`, `missing_dependency`. Se non sai proporre una correzione affidabile, dichiara il limite; non inventare che un filtro risolva un problema strutturale. Il runtime conserva anche i precedenti `targeted_corrections`.

Per una versione corretta leggi anche il precedente artefatto, includilo in `source_files` e indica `baseline_path`. Aggiungi `comparison`: lista di `requirement_id`, `status` tra `improved`, `unchanged`, `regressed`, `not_verified` ed `evidence` puntuale. Il runtime registra gli hash dei due file, rifiuta miglioramenti su byte identici e mantiene non verificato ciò che il collegamento non permette di osservare. Migliorato non significa necessariamente sufficiente: i criteri ancora falliti rimangono falliti.


## Verifica di una prova e chiusura del lavoro

Per la revisione completa usa `"scope":{"kind":"final"}` oppure ometti `scope`. Puoi elencare `requirement_ids` del contratto per documentazione: il verdetto finale controlla comunque tutti i requisiti, anche quelli non elencati. `kind=final` non è un checkpoint e non richiede `question`. Non ripetere un’ispezione già conclusa soltanto per correggere i metadati del rapporto; conserva prodotto, hash, osservazioni e giudizi reali.

Per una prova limitata aggiungi al rapporto `"scope":{"kind":"checkpoint","question":"Domanda concreta della prova","requirement_ids":["id_del_requisito_rischioso"]}`. Seleziona solo ID del contratto: nessun elenco di professioni o tipi di progetto. Il runtime restituisce due verdetti: `checkpoint.status` riguarda la domanda selezionata; `status` riguarda sempre tutti i requisiti finali. Un checkpoint superato non approva il prodotto finale. Riporta anche le mancanze finali, ma distingui una durata/estensione volutamente ridotta dai difetti della tecnica che la prova doveva dimostrare. Non inserire una durata non definitiva e una qualità sensoriale nello stesso criterio: usa requisiti osservabili separati e il metodo pertinente a ciascuno.

`continuation` distingue correzione, completamento della produzione e verifica umana. Se restano solo modalità indisponibili, presenta il prodotto esatto e i sorgenti con i limiti, mantieni `status=review` e chiedi la verifica necessaria. Non ripetere lo stesso incarico e non rigenerare il prodotto per ottenere un ascolto o una visione che il collegamento non offre.


## Rilievi proporzionati e verificabili (rapporti nuovi: versione 2)

I nuovi rapporti usano `review_version: 2` e `findings`. Ogni rilievo contiene `severity` (`blocking`, `advisory`, `uncertain`), `location`, `evidence` e `impact`. Un rilievo bloccante indica anche il `requirement_id` realmente violato. Per ogni criterio obbligatorio `failed` serve almeno un rilievo bloccante: un gusto personale o una finitura facoltativa non dimostrano il fallimento del requisito. Il runtime rifiuta una bocciatura v2 priva di questa motivazione; non la converte in approvazione. I rapporti precedenti rimangono leggibili.

Prima di bocciare, osserva il difetto sul prodotto reale, localizzalo e descrivi cosa impedisce all'utente. Quando disponibili, confronta anche misure, limiti o casi riproducibili: non dedurre una sovrapposizione, un errore di calcolo o una regressione dal solo sospetto. Se la causa è dubbia usa `uncertain`, prova il caso minimo e conserva `not_run` sul requisito non verificato. Le misure non sostituiscono visione o ascolto quando richiesti.

Un consiglio facoltativo usa `advisory` e non diventa una correzione obbligatoria. Per un difetto confermato mantieni il criterio `failed`, proponi una correzione locale, indica i file interessati e il controllo minimo che la conferma. Non ripetere tutte le verifiche già valide, salvo dipendenze o regressioni da controllare.

Esempio di rilievo da adattare alle prove reali: `{"requirement_id":"functional_result","severity":"blocking","location":"Caso di prova e punto del risultato interessato","evidence":"Input effettivo, risultato osservato e risultato atteso","impact":"Impedisce il comportamento richiesto; correggere quel caso senza rifare le parti valide"}`.

### Missing observation is an actionable dependency

Inspect the actual transport and tools before claiming a modality is unavailable. For a PDF, render the **delivered PDF** with an authorized Poppler environment and inspect those page images with a working visual tool; images compiled separately from the authoring source are not the same evidence. If the role lacks an authorized renderer, ask the coordinator to compose a focused verification role rather than regenerating the product.

Split structural correctness and visual legibility into separate observations. If an observation cannot run, keep its status `not_run` and add an explicit limitation to `quality-review.json`:

```json
{"observation_limits":[{"method":"visual","reason":"The selected connection cannot inspect page images.","next_action":"Use a visual-capable reviewer on the saved page images, or request the user's visual check."}]}
```

A criterion waiting for another observation can declare `blocked_by: "visual"` (or another actual method). This never approves it or removes a genuine failure. The coordinator should present saved files and the specific missing check, preserve all valid sources, and avoid repeating the same unsupported verification. Report quota/authentication failures separately from defects in the product.


## Idoneità del metodo e dei sorgenti

Confronta il prodotto con la richiesta e con `capability_rationale` del ruolo, non con il solo formato esportato. Una compilazione riuscita prova la produzione del file, non la correttezza semantica di architetture, processi, geometrie, musica o analisi. Quando la richiesta implica un modello modificabile, verifica i sorgenti pertinenti e la coerenza con ciò che è rappresentato: un impaginato o una conversione non li sostituiscono.

Non richiedere una CLI o una notazione per il solo nome: una soluzione semplice che soddisfa i requisiti resta valida. Se la semplificazione ha perso significato, relazioni, dati o modificabilità richiesti, descrivi la perdita concreta e chiedi una correzione del metodo; non limitarti a suggerire colori o spaziature. Distingui requisiti dell’utente da preferenze del revisore e non imporre una nuova pipeline.
