# Criteri di qualità: Animazione e compositing

EffectCraft dispone di composizioni, keyframe e primitive 3D: questo non equivale a un modellatore/scultore completo o a un rig umano pronto. Non usare una raccolta di cubi come sostituto automatico di un personaggio curato.

1. Prima della coreografia verifica silhouette del personaggio, proporzioni, vista frontale/tre quarti, articolazioni e limiti delle primitive. Se il livello richiesto necessita mesh/rig esterni, verifica import reale e disponibilità; segnala il limite prima di un render lungo.
2. Per danza prepara pose chiave riconoscibili e cue della musica reale; controlla appoggio dei piedi, centro di massa, intersezioni, archi, anticipazione e continuità fra pose. Una sinusoide su tutto il corpo non è una coreografia.
3. Usa easing e sovrapposizione temporale delle articolazioni con intenzione. Mostra un contatto visivo iniziale/medio/finale e i punti di cambio; controlla un ciclo completo prima di estenderlo. Non moltiplicare keyframe senza miglioramento osservabile.
4. Una revisione deve indicare quale difetto visibile cambia e conservare qualità e stile delle parti già valide. Non ridurre fps/risoluzione del definitivo senza motivazione nel brief.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
