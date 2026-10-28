# Criteri di qualità: Disegno tecnico e limiti 3D

La ricetta verificata di CADCraft copre disegno DXF 2D. Una mesh generata da codice e illustrata in tavola resta un prodotto distinto, non un modello parametrico CADCraft.

1. Verifica unità, scala, layer, quote associative, tolleranze e geometrie chiuse; confronta coordinate e dimensioni dopo riapertura.
2. Per un oggetto 3D definisci silhouette e proporzioni prima di dettagli. Se serve un generatore geometrico esterno come sorgente, descrivi esattamente l’editor richiesto e le capacità mancanti; non rifiutare un approccio valido solo perché usa un unico specialista.
3. Una tavola professionale richiede gerarchia degli spessori, quote non sovrapposte, viste allineate, cartiglio leggibile e coerenza fra viste. Render e tavola devono derivare dalla stessa geometria.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
