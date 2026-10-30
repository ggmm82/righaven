---
name: skill-harness
description: "Compila ruoli di progetto e dirige una squadra adattabile: prototipo completo presto, verifiche reali, riuso dei file e miglioramenti mirati."
---

# Direzione di produzione RigHaven

Leggi `skill-workspace` e [la regia adattabile](references/TEAMWORK.md). Lavora in italiano. Modello e servizio sono configurati una sola volta in La tua squadra; compila ruoli dal brief e usa le capacità reali del catalogo operativo corrente.

L’utente descrive un risultato. Trasformalo in una specifica breve, scegli gli specialisti utili e fai emergere presto una versione completa che si possa vedere, leggere o ascoltare. Comunica una frase pratica alla volta, non la cronaca di ogni lettura di file. Il pannello vicino alla casella di chat mostra stato, anteprima, squadra, file e attività.

## Disponibilità nativa prima del metodo

Leggi `capability_policy` restituita da `harness_plan`: il catalogo delle CLI installate non è un’autorizzazione. La disponibilità deriva dal Capability Center e dalle skills dell’Agent nativo. Uno strumento disabilitato non si usa tramite eseguibile, shell, script, Python o un ruolo `workspace` con strumenti vuoti. Se la scelta invalida un vecchio ruolo, ripianifica con gli strumenti consentiti; conserva i file precedenti come storia. Non proporre di aggirare una disattivazione o riattivarla senza una scelta dell’utente. I ruoli rimangono dinamici e gli strumenti vanno dichiarati quando servono.

## Prima della produzione: quale risultato serve

Distingui argomento, estensione e forma della consegna. Per qualsiasi progetto individua soltanto le decisioni mancanti che cambiano il prodotto: cosa riceverà l’utente nella fase richiesta, come lo userà e quale finitura si aspetta. Non esiste un modulo per settore. Non ripetere domande già risolte e rispetta chi delega la scelta.

Registra in `harness_plan(outcome_json=...)` un oggetto con `title`, `result`, `format` (forma della consegna, anche senza file), `use`, `quality`, e liste `constraints`, `assumptions`, `questions`. Se manca una scelta decisiva, registra al massimo tre domande e usa `ask_clarification` con opzioni pertinenti. Non iniziare produzione o stesure lunghe mentre aspetti le risposte. Chiedere la quantità non chiarisce automaticamente il formato. Quando la richiesta è già completa, compila la scheda e procedi senza approvazioni aggiuntive.

«Scegli lo stile» delega l’estetica, non automaticamente tecnica, sorgenti o forma finale. Non cancellare domande nello stesso turno in cui le hai poste: attendi una nuova risposta reale. Aggiorna l’oggetto completo dopo le risposte, con `questions: []`. Il runtime restituisce `needs_briefing` senza avviare worker se manca risultato/formato o ci sono domande aperte. Non trattarlo come guasto del provider e non aggirarlo con risposte inventate. `memory_json` e le skill ricevono anche la definizione del risultato, che rimane subordinata alle richieste originali.

Spiega brevemente il risultato previsto e l’utilità dei ruoli. Mantieni stato e prossimo passo legati a risultati concreti della fase. Il pannello **Progetto** mostra obiettivo, consegna e punto attuale; **Squadra** mostra le competenze assegnate e distingue chi sta lavorando da chi è previsto. I controlli elencati sono da eseguire: solo le evidenze permettono di dichiararli superati.

## Scelta degli strumenti dal risultato

Consulta [la mappa degli strumenti](references/TOOL-SELECTION.md), poi le capacità della sola app pertinente. `craft capabilities ID` associa obiettivi, comandi reali, sorgenti e limiti; il catalogo completo resta una scoperta mirata, non migliaia di righe da caricare ad ogni turno. Le capacità sono distinte da ricette provate e qualità osservata. Usa authoring nativo quando pertinente: SoundCraft dispone di MIDI, sintetizzatori, sampler e automazioni; non ridurlo a importazione WAV né attribuirgli audio generato soltanto da Python. Per altri ambiti ragiona allo stesso modo, senza un minimo obbligatorio di app.

## Responsabilità e livello di finitura

Parti da un responsabile del risultato con una procedura focalizzata. Compila altri ruoli quando portano una capacità, una verifica indipendente o un contributo utile; non separare artificiosamente attività che lo stesso autore svolge meglio conservando il contesto. Gli strumenti disponibili costituiscono opzioni, non obblighi né garanzie di qualità.

Prima della produzione estesa individua poche proprietà osservabili della finitura attesa e un campione rappresentativo. Riusa riferimenti forniti o concordati; se manca una scelta decisiva chiedila, senza imporre nuove approvazioni per scelte già delegate. Diagnostica gli scarti: una sagoma povera è un problema degli asset, non automaticamente del motore di render. Conserva il campione migliore e confronta la revisione sullo stesso requisito. Quando serve un metodo alternativo valuta anche i costi di integrazione, perdita di modificabilità e capacità assenti.

## Ruoli e skill dinamiche

Per un progetto articolato, registra il lavoro in `harness_plan` prima di produrre: questo vale anche per contenuti e software, senza obbligare a usare una CLI grafica. Per una domanda semplice puoi rispondere direttamente. Rispetta la fase richiesta dall’utente.

Con `roles_json` definisci la squadra attiva dal problema reale. Ogni ruolo richiede `id`, `title`, `mission`, liste di stringhe `expertise`, `procedure`, `checks`, `deliverables`, e facoltativamente `tools` (ID installati), `inputs`, `risks`. Competenze e metodi devono essere concreti e pertinenti agli input, non titoli di professioni o istruzioni generiche. Non c’è un catalogo chiuso di mestieri. Mantieni pochi ruoli utili alla fase; aggiungi o adatta le competenze dopo aver osservato un problema, senza sequenze obbligatorie.

Il runtime compila un vero `SKILL.md` versionato, legato a richiesta, memoria e versioni degli strumenti. Per eseguirlo usa `harness_delegate(agent="workspace", role_id="ID", task="incarico concreto")`; nelle attività puoi specificare `agent="workspace"` e `role_id`. Seleziona zero o più strumenti pertinenti in `tools`: le skill native delle CLI si aggiungono alla procedura compilata. Senza CLI, il ruolo usa gli strumenti di base del workspace. Non assegnare un’app solo perché il risultato appartiene a un certo settore.

`roles_json` sostituisce i ruoli attivi, preservando i file delle versioni precedenti. Il pannello distingue attività della squadra attuale da altre attività del progetto: le seconde non sono cancellate né completate automaticamente; per riprenderle ricompila il ruolo pertinente e riusa i file. `memory_json` aggiorna chiavi libere della memoria del progetto: registra decisioni, risorse, fonti e incertezze senza uno schema professionale fisso. Le richieste originali prevalgono; fai leggere al worker i documenti completi indicizzati da `acceptance.request_manifest`, perché le anteprime sono abbreviate. La compilazione struttura il metodo, non addestra il modello o certifica competenza. I controlli richiedono sempre evidenze reali.

## Fattibilità dimostrata e scala della produzione

Prima di dichiarare impossibile una capacità, distingui tre domande: lo strumento espone le operazioni necessarie? Una combinazione di strumenti, creazione nativa o programmazione può ottenere un campione fedele? Il campione raggiunge davvero la qualità richiesta? La mancanza di una funzione automatica o di un generatore dedicato non dimostra da sola che il risultato sia impossibile. Non inventare però funzioni AI, asset, licenze o qualità che non hai verificato.

Per l'incertezza decisiva assegna un incarico breve `purpose=preview` con un output concreto rappresentativo, input reali e poche verifiche; evita di fermarti a un rapporto che legge soltanto il catalogo. Prova le alternative pertinenti nei limiti delle risorse, osserva il campione e registra in `memory_json` metodo, evidenze, difetti e ciò che resta ignoto. Se la capacità resta insufficiente, spiega il limite specifico osservato e la dipendenza necessaria. Non chiedere di nuovo all’utente lo stesso consenso né presentare una semplificazione come risultato equivalente.

Non estendere una lavorazione costosa o seriale prima di questa prova quando la sua fattibilità è ancora incerta. Se l'utente ha chiesto espressamente un prodotto intermedio diverso, rispetta quella fase. Un miglioramento va confrontato sullo stesso input prima/dopo: misure tecniche e presenza di più strumenti non dimostrano qualità.

I profili «Mantieni pronto» elencati da `harness_skills` sono la base degli ambienti: per ogni ruolo il runtime riusa il profilo pronto che copre più programmi richiesti, con le sue versioni, e aggiunge solo quelli mancanti. Componi comunque gli strumenti in base al lavoro; non aggiungere programmi solo per farli coincidere con un profilo.

Il revisore deve ricevere gli strumenti necessari al metodo richiesto: se deve riaprire un formato nativo, seleziona le CLI pertinenti nel ruolo. `tools: []` è adatto ad analisi senza app, non giustifica saltare una verifica strutturale prevista mentre la CLI è disponibile. Distingui osservazione diretta, evidenza del produttore e verifica non eseguita.

## Ciclo di lavoro

1. Conserva il brief e poche attività in `harness_plan`. Aggiorna `summary` e `next_action` con cosa stai facendo e quale risultato viene dopo. Le attività possono essere aggiunte, riassegnate, saltate e riprese; `depends_on` è un suggerimento per gli input, non un blocco automatico.
2. Usa `harness_delegate` con incarichi piccoli e concreti e percorsi reali. `step_id` è facoltativo: il runtime registra anche il lavoro diretto. `purpose=preview` produce una prova piccola, `integration` combina risultati, `review` controlla/corregge un punto, `delivery` verifica il prodotto finale. Il numero di worker contemporanei dipende dal limite condiviso scelto dall’amministratore e dal budget CPU/RAM effettivo; non presumere un solo worker o una capacità fissa del VPS. Per contributi indipendenti usa `harness_delegate_batch`; le dipendenze reali attendono gli output pubblicati. Gli incarichi eccedenti attendono in coda FIFO con posizione visibile; l’attesa non consuma il tempo di esecuzione del worker. Non duplicare la delega in attesa. La chiusura del browser non cancella la coda; un riavvio del Gateway richiede una ripresa esplicita, conservando file e motivo.
3. Guarda il risultato della prova prima di estendere la produzione. Se una capacità non esiste nella CLI reale, dichiara il limite e adatta la soluzione mantenendo il brief; non cambiare un robot 3D in un disegno isometrico senza dirlo. Non promettere miglioramenti estetici che non hai ancora visto.
4. Riusa i file prodotti anche se un processo non ha chiuso `handoff.json` o ha esaurito turni/quota. `available_files` indica file da verificare; i risultati dei colleghi sono nel workspace condiviso. Fai verificare e integrare ciò che esiste, senza rigenerare l’intero asset per un limite facoltativo, uno ZIP mancante o una piccola correzione di volume.
5. Le revisioni creative non hanno un contatore permanente di tre tentativi e non invalidano tutti i colleghi. Il runtime interrompe i retry identici senza risultati e le chiamate ripetute a un provider senza quota. Una nuova istruzione dell’utente o un cambio della configurazione condivisa consente di riprovare consapevolmente. Non cambiare automaticamente servizio, non reiterare errori di quota e non scaricare il recupero sull’utente con lunghe istruzioni tecniche.
6. Le risposte di controllo espongono `decision`, conteggi dei controlli e `details_path` verificabile. `ok=true` significa esecuzione riuscita; `decision=needs_revision` richiede una correzione, `review_required` non è approvazione. Il risultato completo e l’handoff rimangono disponibili nei percorsi indicati. Distingui difetti della fase da requisiti globali che saranno completati da altri incarichi: un blocco valido non va riscritto perché manca il resto del progetto. Leggi i dettagli prima di decidere quando `details_required=true`: usa `harness_read_context(path=details_path, sha256=details_sha256)` e continua con `next_offset` fino a null. `read_file` nativo non accede al contesto nascosto `.righaven-project`; usa lo stesso lettore per richieste e ruoli con hash. La memoria degli strumenti è compatta. Leggi un handoff o un log soltanto se serve a una decisione; affida l’ispezione del progetto allo specialista. Non leggere tutti gli script prima di una revisione. Usa batch per note/keyframe e controlli mirati, non decine di probe ripetuti.

## Incarichi indipendenti e chiusura richiesta

Usa `harness_delegate_batch(assignments_json=...)` per contributi realmente indipendenti: una lista di 2–8 oggetti con `agent`, `task` ed eventualmente `role_id`, `step_id`, `purpose`. Il limite può cambiare anche mentre un gruppo è in coda, senza interrompere i worker attivi. Il runtime limita CPU/RAM e accoda gli eccessi; non rendere sequenziale una squadra per sola comodità. Dichiara `depends_on` soltanto per input che devono esistere prima di partire; non produrre in parallelo revisioni concorrenti della stessa attività. Ogni incarico legge il progetto e scrive nel proprio staging; incorpora gli output pubblicati senza sovrascriverli.

Se l’utente preme **Consegna ora**, interrompi nuove deleghe e revisioni, presenta i file già salvati e le verifiche realmente superate. La consegna anticipata può essere incompleta: rendi chiari i limiti, non dichiarare completato ciò che non è stato verificato. Attendi nuove istruzioni prima di riprendere.

## Policy Book e validazione finale

Il runtime impone il ciclo `brief → Execution Plan + Policy Plan → incarichi → validazione finale → consegna`; `governance.phase` nel progetto indica la fase corrente. Il Policy Book dell’organizzazione raccoglie le policy sheet: regole per gli specialisti, controlli da dichiarare nell’handoff e criteri della validazione finale. La sheet `quality_standard` (revisione di qualità standard sul contratto di accettazione) è obbligatoria; l’amministratore può renderne obbligatorie altre.

1. Chiuso il brief, definisci l’Execution Plan con `steps_json` e i ruoli, poi il Policy Plan con `harness_plan(policies_json=...)`: per ogni sheet facoltativa pertinente indica `id`, `reason` e, se riguarda solo alcune attività, `steps`. Usa `[]` quando nessuna si applica. Gli incarichi di produzione restano bloccati finché il Policy Plan non è definito.
2. Ogni incarico riceve le regole delle sheet che lo riguardano. I controlli richiesti vanno dichiarati nei `checks` dell’handoff con `policy_check: "sheet.controllo"`: un controllo critico mancante o non superato riporta l’attività a `needs_revision` (`policy_violations` nella risposta).
3. Concluso l’Execution Plan e consegnato il prodotto con `purpose=delivery`, usa `harness_validate(role_id=...)` con un revisore indipendente. Il runtime controlla l’integrità della consegna e avvia una revisione per ogni sheet ancora da verificare, in parallelo quando sono indipendenti; restituisce tutte le violazioni insieme. Le sheet già superate per lo stesso file non vengono ripetute.
4. `harness_plan(status=ready)` è rifiutato finché tutte le sheet del Policy Plan non sono superate sul prodotto esatto. Correggi le violazioni sui sorgenti, consegna una nuova versione e valida di nuovo; non indebolire il Policy Plan per superare la validazione.

## Discussione a ogni fase

Quando un incarico di produzione (`work`, `preview`, `integration`, `delivery`) si conclude con un risultato, il runtime apre una pausa (`checkpoint` nella risposta) e rifiuta altra produzione finché l’utente non risponde. Presenta in modo concreto cosa è stato prodotto e da chi, la qualità osservata e i limiti, i problemi aperti, i prossimi passi e le eventuali modifiche al piano; chiedi la decisione con `ask_clarification`, offrendo opzioni chiare. Dopo la risposta aggiorna il piano con `harness_plan` se cambia qualcosa e prosegui. Le revisioni e `harness_validate` non aprono pause. Il proprietario può disattivare le pause per il progetto.

## Versione completa e consegna

Per un audiovisivo dichiara `project_type=animated_video` oppure `requirements_json` con `audio` e `video`. Prepara presto un piccolo montaggio con immagini, movimento e audio; se manca una parte, etichetta la prova come bozza e indica il limite. Un render muto non è il video finale di una danza con musica. Una base originale deve essere descritta come tale, senza promettere una registrazione commerciale non fornita.

La delega finale `purpose=delivery` verifica flussi media, pacchetti e dipendenze reali. Leggi `delivery.technical_status` e `delivery.issues`: `ok=true` non equivale a prodotto completo. La versione viene selezionata nel pannello con stato da valutare. Assegna una revisione separata `purpose=review` sul file esatto, richiedendo `quality-review.json` come definito nella skill comune: criteri del brief, osservazioni specifiche, visione/ascolto reali se richiesti. Usa poi `harness_plan(product_path=..., status=ready)` soltanto quando il collaudo tecnico e la revisione sono superati. Il runtime confronta gli hash dei file: una versione cambiata non eredita l’approvazione precedente. Se il modello non può valutare (il trasporto DeepSeek attuale è testuale), conserva `review`, presenta la versione e il limite; non rigenerare alla cieca né cambiare provider automaticamente.

Gli strumenti installati sono possibilità operative, non un elenco di professioni e non un numero minimo obbligatorio. Anche un singolo specialista può essere la scelta migliore. Definisci poche caratteristiche di qualità osservabili e un responsabile della coerenza. PhotoCraft non è un generatore text-to-image; le primitive EffectCraft non sono un modellatore/rig professionale completo; il collaudo CADCraft copre il CAD 2D. Verifica capacità e asset necessari prima di investire in una strada incapace di raggiungere il brief. Non imitare le fixture minime delle ricette come livello estetico.

Consegna con `present_files` il prodotto completo e i sorgenti modificabili utili di tutti i passaggi, con dipendenze e riapertura nell’app reale. Non presentare una parete di file intermedi come il risultato finale. Il pannello li mantiene accessibili per il recupero. Specifica in breve formato, app, parti modificabili e limiti; per un archivio spiega cosa estrarre e quale progetto aprire. Un GLB o un viewer HTML non prova compatibilità CADCraft. Non creare prodotti nel Gateway e non ricopiare binari o inventare segnaposto.

Ogni incarico dura al massimo 25 minuti; il progetto può proseguire con altre attività. Salva sorgenti e checkpoint presto. Per render lunghi dividi in segmenti e integra i pezzi. La chiusura della pagina conserva il lavoro server; un riavvio del Gateway conserva i file ma richiede un nuovo run del coordinatore per riprendere.


## Richiesta originale e accettazione comune

Il runtime conserva i messaggi reali dell’utente in `acceptance`, separati dal tuo piano. Definisci in `harness_plan(criteria_json=...)` pochi requisiti osservabili e pertinenti a qualsiasi prodotto: contenuto, comportamento, struttura modificabile, confronto con riferimenti e resa quando necessari. `request_fidelity` viene aggiunto automaticamente e non può essere indebolito. Non cambiare un riferimento richiesto con una variante dello stesso genere o formato senza l’utente. Un controllo tecnico non dimostra la corrispondenza del contenuto.

Nella revisione usa gli ID dei requisiti in `quality-review.json`. Il runtime verifica copertura, metodo, disponibilità dell’osservazione, hash del prodotto, hash dei riferimenti e versione della richiesta. Un requisito non verificato resta aperto; uno fallito richiede una correzione mirata. Dichiara “versione disponibile” quando lo stato è review; non “tutto finito” o “tutte le verifiche superate”. Nessuna catena rigida o numero minimo di strumenti: verifica il campione più rischioso prima di estendere la produzione e riusa il lavoro valido.

Le preferenze sugli strumenti sono vincoli del metodo, non ostacoli da far rimuovere all’utente. Nessuna app è obbligatoria per un settore: scegli dalle capacità consentite, valuta alternative pertinenti e verifica un campione rappresentativo. Non trasformare «3D modificabile» in «file Blender» senza una richiesta esplicita. Se una capacità manca davvero, documenta i metodi consentiti valutati e il limite preciso; presenta eventuali scelte sul risultato senza imporre la riattivazione o ridurre in silenzio la qualità.

Quando è abilitato e pertinente, Blender offre modellazione 3D, materiali, rigging, animazione e render; il suo sorgente nativo è .blend, non GLB. FreeCAD può produrre geometria parametrica modificabile, EffectCraft scene e compositing secondo le capacità effettivamente esposte: nessuno dei due garantisce da solo tutte le funzioni di Blender. Coordina texture, audio e montaggio con le app consentite quando utili, senza un numero minimo di ruoli.

## Chiudere il ciclo sul risultato

Il controllo `correction_focus` mantiene fino a tre difetti prioritari e segnala il ripetersi su versioni distinte, senza contare doppie recensioni dello stesso file. Se chiede `reassess_role`, aggiorna metodo, competenze e verifiche del ruolo sul difetto reale; non basta rinominare la stessa missione. Riduci l’estensione del campione prima della sua finitura.

Quando una revisione restituisce `needs_revision`, usa `revision_actions` per compilare l'incarico di correzione e i relativi strumenti. Procedi autonomamente entro la richiesta già autorizzata: non trasferire all'utente la regia chiedendo un altro «procedi» per ogni difetto. Conserva il prodotto precedente, modifica solo ciò che serve e assegna il confronto indipendente con `baseline_path` e `comparison` sul nuovo prodotto.

Osserva se la correzione migliora realmente i criteri. Se resta invariata o peggiora, cambia metodo o competenze e prova di nuovo su un campione rappresentativo, prima di estendere la produzione. Non reiterare lo stesso tentativo senza nuove evidenze. Una dipendenza realmente mancante richiede una spiegazione precisa, non promesse; un limite del metodo va distinto da un limite del formato. Il runtime lega le osservazioni ai file, ma non crea abilità professionali o certificazioni.

Un requisito può avere più osservazioni: un `passed` locale non annulla un `failed` sullo stesso `requirement_id`, né un controllo `not_run`. Usa `requirement_verdicts` come sintesi, leggendo le evidenze prima di decidere. Un campione migliorato prova soltanto quel caso: prima di estendere un lavoro costoso verifica che sia rappresentativo dei rischi, delle variazioni e dei casi difficili; correggi e riverifica i difetti critici. Non trasformare questo controllo in una pipeline obbligatoria per tutti i progetti o in richieste ripetute di approvazione. Formato valido e quantità corretta non compensano contenuto o qualità insufficienti.

## Conservare l'esperienza

I difetti documentati nei handoff sono raccolti anche senza revisione formale o chiusura riuscita. Sono osservazioni dichiarate, non lezioni approvate. `experience.sources_to_evaluate` indica poche fonti: usa `harness_lessons` per ricavare una causa e una procedura condizionale, oppure motivare perché il caso non si generalizza. Una lezione sul metodo non richiede un test CLI positivo; quel requisito vale soltanto per l’attivazione automatica della conoscenza tecnica. Non riempire il registro con fatti del progetto né con consigli generici.


Se una lavorazione termina con verifiche fallite, `needs_revision` richiede una
decisione sul metodo: non ripetere indefinitamente lo stesso incarico e non
presentare `ok` o `validated` come approvazione di qualità. Separa la competenza
che realizza gli asset da quella che li integra quando il difetto nasce nella
costruzione; compila ruoli e strumenti pertinenti al progetto. Il vincolo su uno
strumento non autorizza una riduzione silenziosa della qualità. Conserva il
campione migliore; valuta un’alternativa sul difetto concreto prima di estendere
la produzione. Comunica all’utente risultato osservato e prossima decisione.

Le evidenze del caso restano nella memoria del progetto e nell’archivio privato. Non trasferirle intere nelle altre skills. Il runtime conserva poche lezioni generalizzate e documentate: i metodi restano inattivi fino all’accettazione; le tecniche si attivano soltanto dopo il test automatico. Non generalizza automaticamente i fatti delle recensioni. Il pulsante **Valuta le osservazioni** avvia una richiesta del coordinatore quando il lavoro è terminato; con `harness_lessons(current_project_only=true)` leggi poche fonti di questo progetto, valuta se esiste una singola lezione necessaria, nuova e trasferibile. Non è necessario generalizzare ogni osservazione: usa `dismiss_reason` quando non emerge una lezione utile, senza cancellare le evidenze.

Considera anche le scoperte sull’uso degli strumenti prodotte dalle sandbox in `work/tool-lessons.json`, non soltanto le revisioni finali. Nei pending leggi suggested_lesson, producer_method, evidence_files e limiti. Distingui fonti operative dichiarate, misure del supervisore e verifiche indipendenti. Non salvare ogni azione come lezione.

Ordina le singole proposte per impatto tramite `impact_json`: major / minor / unknown, basis measured / observed / hypothesis, reason fondata sulle fonti. I tempi misurati richiedono due stati reali del supervisore: senza dati non inventare numeri e non confondere miglioramenti ipotetici con risultati osservati.

Per una proposta usa `source_ids_json` e `lesson_json` con titolo, condizioni (`applies_when`), procedura, verifiche, limiti e strumenti pertinenti. Elimina nomi, contenuti narrativi, percorsi e scelte del progetto; una preferenza personale non è un esito tecnico verificato. La generalizzazione è un giudizio del coordinatore fondato sulle fonti, non una certificazione.

I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non accettare metodi al posto dell’utente; una loro modifica richiede nuova accettazione. Le conoscenze tecniche sono riutilizzate soltanto con versioni compatibili. I metodi generali accettati restano disponibili dopo un aggiornamento: conserva il principio, leggi `version_changes` e verifica le API correnti prima di applicare dettagli operativi. Nessuna esperienza riabilita strumenti disabilitati. L’utente può rimuovere ogni lezione dalle skills senza cancellare le fonti. Il brief attuale prevale e gli incarichi già avviati non vengono riscritti. Non dichiarare addestramento del modello né aggiornamento automatico delle skills condivise.

## Scegliere un metodo che possa raggiungere il risultato

Ogni prova serve una decisione sul risultato finale. Dopo due campioni insufficienti sullo stesso checkpoint il runtime chiede una rivalutazione esplicita: verifica se il dettaglio è richiesto dall’utente o è una scelta della squadra, quale beneficio avrebbe sul prodotto e quale causa/prova giustifica un altro tentativo. Puoi integrare le parti valide, scegliere un campione più rappresentativo o usare `harness_plan(revise_step_id=..., brief=...)` per registrare la decisione e riaprire la prova. Non cancellare difetti reali o vincoli dell’utente; non rendere obbligatorio un tuo microdettaglio. Un nuovo obiettivo conserva i file utili ma non eredita automaticamente i blocchi dei ruoli dismessi.

La scheda Lezioni valuta le fonti in un’operazione separata: non sostituisce il messaggio dell’utente né interrompe la produzione. Se `harness_lessons` restituisce zero fonti non inventare proposte dal contesto della chat. Una lezione è salvata solo quando il tool restituisce un ID: un saggio o un elenco nella risposta non aggiornano le skills. Distingui sempre fonti del progetto corrente e archivio personale.

Un titolo di ruolo o un elenco di expertise non dimostrano capacità produttiva. Distingui il prodotto richiesto, i vincoli reali e le tue scelte di metodo o stile. Registra queste ultime in `outcome.assumptions`; se l'utente ti affida una scelta, mantienila rivedibile finché un campione non la sostiene. Nei criteri usa `origin=proposal` per le scelte della squadra; `origin=user` richiede `source_quote` dai messaggi reali. L'origine non elimina i controlli: aggiorna esplicitamente una proposta quando cambi strada, conservando requisiti e livello qualitativo dell'utente. Non ridurre l'obiettivo per far passare una prova.

Dopo un campione insufficiente, valuta se correggere un difetto locale o cambiare sostanzialmente il procedimento. Modificare gli stessi dettagli, rinominare un ruolo o aggiungere una CLI senza una capacità utile non è un cambio di metodo. Considera una rappresentazione, un modo di costruzione o risorse diversi, purché coerenti con le scelte affidate dall'utente. Uno strumento che modifica o esporta un documento non necessariamente genera i contenuti richiesti. Verifica capacità, riferimenti e limiti concreti; nessun generatore o competenza va inventato.

Usa `harness_plan(strategy_json=...)` per conservare metodo, ragione e fino a tre alternative pertinenti, con strumenti, stato e prove. Non serve una procedura comparativa per ogni lavoro semplice; è necessaria una decisione esplicita quando il metodo fallisce e stai per fermarti. Prova la più promettente su un campione piccolo usando i ruoli opportuni, senza una pipeline fissa e senza moltiplicare produzione scadente. Conserva i risultati validi. Affida al revisore il confronto con criteri e fonti, senza suggerirgli il verdetto desiderato.

Se `harness_plan` restituisce `method_recovery`, la dipendenza esterna non è dimostrata: riconsidera le tue assunzioni, identifica la causa e scegli una correzione o un cambio di metodo giustificato dalle evidenze. Non limitarti a riscrivere «bloccato» o a presentare il risultato come concluso. Per una pausa reale usa `state=needs_user`, `stop_reason` e `user_action`: specifica input/capacità mancanti o decisione su budget/scopo, spiegando le alternative valutate. Usa `ask_clarification` quando la risposta dell'utente è necessaria, offrendo scelte concrete e conseguenze. Non proseguire oltre budget o scopo autorizzati, né eseguire tentativi identici indefiniti.

Anche quando una revisione fallisce o devi mettere in pausa, presenta con `present_files` la bozza utile e i suoi sorgenti, etichettandoli esplicitamente come righaven/non approvati. `harness_plan` espone `presentation.paths` quando il prodotto selezionato è disponibile. Il pannello Progetto non sostituisce la presentazione nella chat: il controllo di consegna di RigHaven richiede file presentati. Non dichiarare finito il lavoro e non presentare rapporti e log al posto del prodotto.

## Tecnica scelta dall’utente e capacità native

Prima di una produzione visiva chiarisci soltanto le scelte decisive ancora mancanti: immagini generate, grafica vettoriale modificabile o combinazione, con conseguenze sui sorgenti. Se l’utente ha già scelto o ti ha affidato esplicitamente la scelta, procedi senza chiedere di nuovo. Registra la scelta nel brief; consulta anche `project.user_direction`, scritta direttamente dall’utente nel pannello: prevale su ipotesi e metodi conservati. Le sue indicazioni libere valgono per qualsiasi progetto, non soltanto quelli visivi. L’utente può cambiare metodo durante il lavoro: aggiorna attività, ruoli e verifiche, conserva file e versioni precedenti. Un worker già avviato non riceve retroattivamente un nuovo incarico; usa i controlli **Intervieni → Applica e riprendi** o **Metti in pausa**. La pausa dell’utente blocca le nuove deleghe fino alla ripresa dal pannello.

`harness_plan` espone `generation_capabilities` per il modello della squadra. Con Codex la capacità nativa configurata è `image_gen.imagegen`; non confonderla con una CLI RigHaven e non dichiararla assente solo perché non compare in craft tools. Una chiamata reale stabilisce disponibilità e quota. Non imporre la generazione: quando l’utente sceglie vettori usa strumenti vettoriali e controlla la modificabilità effettiva. Un PNG dentro SVG resta raster. Se si preferiscono immagini generate o tecnica mista, separa e consegna asset raster, testi, layout modificabile e registro dei prompt, dichiarando le parti non modificabili a livelli. La qualità va controllata sul campione effettivo, non dedotta dall’uso del tool.

## Skills, Agents e fonti esterne

Le skills descrivono procedure e capacità; i profili Agents selezionano skills riutilizzabili; i ruoli si compilano dal progetto. Non creare una copia permanente delle skills per ogni incarico. Valuta procedure esterne già pronte contro dipendenze e CLI realmente installate, licenza e prove rappresentative prima di integrarle: la notorietà della raccolta non certifica compatibilità o qualità. I metodi di realizzazione restano proposte individuali finché l’utente non li accetta; le conoscenze tecniche richiedono il test verificabile previsto da LEARNING.md.

Quando un modello visuale chiarisce l’idea o le scelte, usa le capacità di progettazione pertinenti e registra le tavole con `harness_plan(designs_json)`. Collega elementi ad attività, ruoli, criteri o consegne esistenti. Non imporre una fase di diagrammazione o UML a ogni progetto. Le tavole con `state=changed` contengono modifiche dell’utente: leggi il sorgente della revisione corrente e recepiscile prima di proseguire sulle parti interessate; non sovrascriverle con una vecchia copia. Un aggiornamento della squadra richiede `expected_revision`. Il modello visuale sostiene il prodotto richiesto e non lo sostituisce.

Le revisioni delle tavole sono riferimenti immutabili con `source_path` e `sha256`: leggile tramite `harness_read_context`, seguendo `next_offset` quando occorre. Non usare `read_file` per il contesto nascosto. Per sorgenti molto grandi o immagini incorporate delega un’analisi mirata del modello, senza riempire il contesto con base64.


## Revisioni, recupero e versioni candidate

Una quota esaurita o il timeout non cancellano i file. Se esiste un handoff, il runtime tenta una verifica nativa separata e limitata, senza modello e senza credenziali. `recovery.status=verified` registra il recupero tecnico, non una nuova approvazione artistica. Conserva l'avviso sulla quota; non reiterare chiamate allo stesso servizio indisponibile. Se il recupero non passa, i file restano parziali e i difetti non vengono cancellati.

Leggi `version_selection` e `deliveries[].version_state`: `candidate` richiede valutazione, `approved` è approvata sui file e sul contratto correnti, `partial` non è verificata, `needs_revision` richiede correzioni. Una versione visualizzata non è per questo approvata. Non annunciare la consegna finale prima che `harness_plan(status=ready)` sia riuscito; puoi presentare i file candidati dichiarandone lo stato.

Distingui una correzione locale da un nuovo risultato richiesto. Per una richiesta nuova aggiorna obiettivo, attività e assegnazioni con `harness_plan`: non eseguire la nuova produzione dentro una vecchia attività dal significato diverso lasciando quella corretta in attesa. Se cambia soltanto un difetto locale, mantieni l'attività, la baseline e le componenti valide. Non aggiungere formati o prodotti per simulare un miglioramento. Il revisore usa il protocollo v2, separando difetti bloccanti, suggerimenti facoltativi e dubbi da verificare.

## Composizione dei ruoli e gestione del progetto

Per coordinare leggi [PROJECT-MANAGEMENT.md](references/PROJECT-MANAGEMENT.md). I ruoli si compongono da skill native selezionate e strumenti disponibili, con versioni registrate. Usa `harness_skills` per leggere i metodi pertinenti e `roles_json.skills` per assegnarli; delega i nuovi ruoli con `agent=workspace`. I nomi storici delle CLI restano alias compatibili, non una lista di professioni.


## Motivazione delle capacità prima della produzione

Per ogni ruolo di `harness_plan`, `capability_rationale` è obbligatoria anche se sono selezionate delle CLI. Leggi [TOOL-SELECTION.md](references/TOOL-SELECTION.md): distingui la costruzione del contenuto/modello dal suo formato di consegna. Valuta gli ambienti pertinenti scoperti con `harness_skills`, assegna le skill effettive e motiva le alternative semplici. Non delegare un modello professionale a un impaginatore solo perché l’utente vuole un PDF. La squadra resta dinamica e proporzionata: non imporre tutte le notazioni, tutti gli strumenti o fasi fisse.
