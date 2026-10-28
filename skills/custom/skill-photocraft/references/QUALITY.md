# Criteri di qualità: Direzione visiva e immagini

PhotoCraft è un editor raster, non un generatore text-to-image. Usalo per compositing, texture dipinte, maschere e correzioni; non promettere fotografie o concept complessi generati da una descrizione senza una sorgente o un motore disponibile.

1. Definisci silhouette, palette limitata, gerarchia dei valori e direzione della luce; prepara una tavola di stile del contenuto reale prima di produrre molte texture.
2. Controlla a 100% bordi, aliasing, aloni alpha, ripetizione delle texture e risoluzione; per PBR separa base color (senza ombre dipinte), roughness e normal solo quando realmente supportate.
3. Confronta prima/dopo sul soggetto effettivo, non solo su campioni di colore. Materiali ben nominati non dimostrano che il renderer li usi. Conserva livelli e maschere nel sorgente.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
