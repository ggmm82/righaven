# Criteri di qualità: Fogli di calcolo

Un workbook professionale deve essere verificabile e riutilizzabile; una tabella colorata senza formule corrette non basta.

1. Separa input, ipotesi, calcoli e risultati; usa formule verificabili e unità esplicite.
2. Prova valori limite, totali di controllo, riferimenti fra fogli, filtri e ricalcolo dopo riapertura; nessun #REF/#DIV0 nascosto.
3. Controlla formati data/numero, leggibilità, grafici e stampa; documenta dipendenze esterne e consegna formule, non screenshot.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
