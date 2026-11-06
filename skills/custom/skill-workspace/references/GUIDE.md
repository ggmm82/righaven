# Guida della consegna, per chi deve usarla

La guida spiega il progetto e come riprenderlo. Il registro conserva le operazioni; le lezioni conservano regole generali approvate. Non sostituire uno di questi documenti con l'altro.

Durante la produzione mantieni `work/method.json` con `approach`, `steps`, `scripts`, `limits`: descrivi quello che hai effettivamente eseguito, distinguendo costruzione, importazione, conversione, montaggio, calcolo e verifica. Un formato nativo importato non dimostra che il contenuto sia stato creato con quell'app. Non elencare tutti gli strumenti installati come strumenti usati.

Per una consegna utilizzabile prepara anche `work/guide.json`. È documentazione per l'utente, non un altro protocollo che blocca i file se manca. Usa questo schema generale, adattato a qualsiasi progetto:

```json
{
  "overview": "Che cosa contiene questa versione e da dove cominciare",
  "use": ["Passaggi reali per aprire, usare o riprodurre il risultato"],
  "editing": [
    {
      "goal": "Una modifica concreta che l'utente potrebbe voler fare",
      "files": ["percorso/relativo/del/sorgente-consegnato"],
      "steps": ["Che cosa modificare e come ottenere un nuovo risultato"],
      "check": "Come controllare che la modifica funzioni"
    }
  ],
  "limits": ["Prerequisiti, passaggi non provati e limiti della modifica"]
}
```

Massimo 8 istruzioni d'uso, 8 modifiche, 8 passi per modifica e 12 file per modifica. Indica file reali della consegna con percorsi relativi alla cartella del job o assoluti sotto `/mnt/user-data/outputs`. Il runtime collega soltanto file effettivamente consegnati e disponibili. Descrivi prerequisiti, applicazioni/versioni e dipendenze necessarie, evitando promesse di apertura GUI quando hai provato solo la CLI. Includi comandi di riproduzione solo se realmente eseguiti; spiega se rigenerare un asset sovrascrive modifiche manuali. Le istruzioni devono accompagnare il progetto, non richiedere un nuovo incarico per capire come usarlo.

Prima di chiudere confronta la guida con i file presenti: quale file è il risultato corrente, quali sono i sorgenti, cosa cambia rispetto alla versione precedente e quali verifiche/limiti rimangono. Se correggi solo testo, metadati o confezionamento, dichiaralo. Le procedure delle lavorazioni precedenti rimangono nella storia: non attribuire alla nuova versione una ricostruzione mai eseguita.

Il runtime rende la guida consultabile nella sezione Risultato e scaricabile insieme agli originali in un pacchetto esterno. Gli archivi sorgenti già verificati conservano i loro byte e le loro prove. La guida non approva automaticamente il prodotto e non attiva lezioni: una procedura descritta diventa esperienza generale soltanto con la distinta politica delle lezioni.
