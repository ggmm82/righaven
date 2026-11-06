# Criteri di qualità: Musica e sound design

SoundCraft è una DAW con strumenti e sintesi disponibili nel registro, non un generatore musicale o una libreria orchestrale garantita. Programmi General MIDI non garantiscono timbri realistici.

1. Definisci funzione musicale, tempo, metrica, durata e cue; scegli strumentazione coerente e arrangiamento con struttura (ingresso, sviluppo, chiusura), non un loop casuale prolungato.
2. Se arriva un MIDI, preserva e verifica tempo, canali, note, program change e controller; dichiara ciò che il synth reinterpreta. Non vendere una sintesi locale come registrazione originale.
3. Controlla clipping, picco reale, loudness e silenzi con misure; ascolta quando il motore lo consente. Valuta melodia, armonia, groove, bilanciamento e finale: il valore RMS da solo non basta.
4. Consegna sessione con tracce, strumenti e risorse; riapri dopo trasferimento e fai un bounce breve per verificare routing e presenza di tutte le parti.

Questi criteri guidano produzione e revisione; le piccole fixture di CLI-RECIPE.md collaudano i comandi, non sono il livello estetico da imitare. Adatta il lavoro al brief e alle referenze dell’utente. Mantieni un singolo responsabile della coerenza e chiama colleghi soltanto per competenze necessarie, senza imporre tutti i 13 strumenti.

Per una revisione separata usa il protocollo quality-review.json della skill comune: osservazioni specifiche sul risultato esatto, difetti con priorità e correzione mirata. Non confondere misure numeriche con visione/ascolto; se la modalità non è disponibile registra not_run e chiedi una valutazione del risultato, senza rigenerare alla cieca.
