# Criteri di qualità: Grafica vettoriale

Scegli vettori per forme, marchi e illustrazioni scalabili; non simulare fotografie con migliaia di forme se il brief richiede un’immagine realistica.

1. Verifica silhouette e leggibilità alle dimensioni d’uso, spessori coerenti, spazi negativi e allineamenti ottici.
2. Controlla nodi inutili, curve spezzate, contorni aperti, stroke convertiti quando necessario, viewBox e clipping.
3. Conserva gruppi e testi dove editabili; per font mancanti dichiara sostituzioni o conserva una versione tracciata separata. Apri SVG esportato e sorgente.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
