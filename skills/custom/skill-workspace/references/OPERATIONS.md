## Collaborazione e salvataggio progressivo

Gli incarichi possono essere prove, revisioni o integrazioni di lavoro già prodotto. Mantieni il tuo ruolo e usa gli input pertinenti dei colleghi, anche quando il loro processo è terminato senza handoff. Prima controlla che i file esistano e siano utilizzabili. Elenca in `source_files` soltanto gli input effettivamente usati, con verifiche di importazione e limiti. Non serve ricreare una dipendenza per soddisfare una sequenza o un conteggio.

Salva il sorgente presto e aggiorna `work/checkpoint.json` con azioni concluse, percorsi, azioni mancanti e prossima operazione. Ogni incarico ha 25 minuti; se serve più tempo, lascia file utilizzabili e una ripresa mirata. Un file provvisorio resta da verificare, ma non va scartato solo per una chiusura formale mancante. Se riprendi un progetto, porta il lavoro valido nella nuova cartella e ripara i collegamenti, senza sovrascrivere gli input.

Produci presto una prova piccola e completa quando richiesta. Raggruppa note, keyframe e operazioni ripetitive in script o batch: non consumare un turno LLM per ogni proprietà. Riusa schemi e discovery già salvati; consulta la CLI solo per il comando che serve. Distingui verifiche essenziali da limiti facoltativi; non dichiarare visione/ascolto o una GUI provata se non disponibili. I programmi di supporto non dimostrano l’uso della CLI né la qualità artistica.

Per il prodotto completo preserva sorgenti intermedi e dipendenze utili, oltre agli export. La delega finale può includere requisiti media: il runtime controlla nel worker la presenza effettiva dei flussi audio/video e l’audio non silenzioso. Non consegnare un render muto come video musicale definitivo.


## Lavori pesanti: un processo, checkpoint e risorse reali

Il budget CPU/RAM è unico in La tua squadra; il Gateway lo passa al worker. Non presumere GPU o risorse illimitate. Per render, conversioni o export lunghi usa il supervisore comune:

```bash
python3 /opt/righaven-worker/operations.py --key "export-versione-1" --label "Esportazione finale" --timeout 1200 -- programma argomento1 argomento2
```

Usa una chiave stabile per lo stesso lavoro e i suoi input; cambia versione solo quando cambiano davvero. Il supervisore registra stato e log in `work/operations`, impedisce processi pesanti contemporanei e termina l'intero gruppo di processi al timeout. Se dice che un processo è ancora attivo, osservane lo stato e attendi: non cambiare chiave e non avviare un altro render o wrapper in background. Non usare `nohup`, shell disaccoppiate o cicli LLM di polling. Il pannello riceve avanzamento e RAM senza chiamate al modello. I percorsi dei log sono diagnostica, non consegne.

Prima di una produzione costosa misura un campione rappresentativo senza alterare il risultato finale richiesto. Distingui stima da misura; salva il sorgente e un checkpoint prima di partire. Blender `render` esegue automaticamente un campione con `blender.profile`, riutilizzato se progetto e budget sono invariati. La stima indicativa comprende il costo di avvio e può variare molto; non è una promessa né una ragione per abbassare in silenzio la qualità. Se il costo eccede il budget residuo, conserva il progetto e pianifica una continuazione mirata o un'ottimizzazione fedele al brief.

`oom_kills` positivo conferma memoria esaurita nel worker; codice 137 da solo indica arresto forzato con causa da verificare. Dopo memoria esaurita non ripetere identico il lavoro negli stessi limiti: salva il checkpoint e segnala il budget da correggere. I lavori già attivi non cambiano risorse quando si salva il pannello. Un timeout interrompe la singola operazione, non autorizza a dichiarare il prodotto completato.

Usa `RIGHAVEN_CPU_THREADS` per i parametri di threading delle CLI (per esempio FFmpeg `-threads`), senza assumere il numero di CPU fisiche. Il budget è un limite del worker, non una prenotazione di RAM né una garanzia di prestazioni del VPS.

