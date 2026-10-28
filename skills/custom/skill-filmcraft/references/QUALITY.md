# Criteri di qualità: Montaggio e consegna audiovisiva

FilmCraft monta media esistenti: non migliora da solo un modello o una danza scadenti. Rendi verificabili le scelte di ritmo, taglio, sincronizzazione e presentazione.

1. Confronta timeline e brief: durata, aspect ratio, risoluzione, fps, cue musicali. Una prova a 960×540 non diventa automaticamente il master richiesto; stabilisci il formato finale prima di esportare.
2. Rivedi inizio, tagli, raccordi, finale e sincronizzazione. Non nascondere un salto di posa con una dissolvenza se crea doppie sagome; chiedi la correzione del solo raccordo al responsabile movimento.
3. Il video musicale richiede ascolto o un limite esplicito. Rumore non silenzioso non dimostra musica appropriata. Controlla anche clipping, dinamica e rapporto con il ritmo.
4. Confeziona sorgenti con il tool fidato source_packages.py pack; collauda da una cartella diversa. La release 0.7.2 risolve i media relativi dalla working directory: servono preparazione locale o Link Media. Indica il .locale.fcproj e la versione app provata.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
