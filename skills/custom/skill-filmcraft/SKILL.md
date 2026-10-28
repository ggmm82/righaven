---
name: skill-filmcraft
description: "Montaggio, sequenze, composizione di contributi, colore e master audiovisivo. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Montaggio video

Specialista: `filmcraft` per `harness_delegate`; nome della skill: `skill-filmcraft`.
CLI: `filmcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Montaggio, sequenze, composizione di contributi, colore e master audiovisivo. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities filmcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa FilmCraft per montaggio, timeline e integrazione audio/video. Usa EffectCraft per composizioni animate e SoundCraft per un mix multitraccia complesso.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help filmcraft` e consulta `/opt/righaven/reference/filmcraft/help.txt`.
3. Salva il registro reale con `craft commands filmcraft > "$RIGHAVEN_OUTPUT_DIR/work/filmcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools filmcraft --out "$RIGHAVEN_OUTPUT_DIR/work/filmcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch filmcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Ispeziona ciascun media con probe/ffprobe: durata, codec, frame rate, dimensioni, rotazione, canali e sample rate. Stabilisci risoluzione, fps, aspect ratio e durata di destinazione.
2. Crea una timeline con tagli e sincronizzazione espliciti; conserva i media collegati. Esegui una breve esportazione di prova con rendering CPU prima di render lunghi sulla VPS.
3. Verifica inizio, transizioni, sincronizzazione labiale, titoli e finale. Esporta il progetto modificabile e un file con codec/container concordati; non presumere che l’estensione determini il codec.

## Diagnosi e recupero CLI

- Se l’export è vuoto o troncato, verifica media risolti, intervallo della timeline e unità temporali richieste dallo schema: frame e secondi non sono intercambiabili.
- Se il rendering fallisce sulla VPS, prova prima un segmento breve in CPU con la stessa risoluzione e codec. Non ripetere l’intera esportazione prima di aver letto stderr e verificato spazio e dipendenze.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Con ffprobe confronta durata, fps, risoluzione e stream audio con il brief; controlla media mancanti e decodifica del file.
- Genera fotogrammi iniziale/intermedi/finale e campioni delle transizioni; un frame corretto non dimostra la qualità dell’intero video.
- Indica separatamente controlli tecnici, visione e ascolto eseguiti. Consegna progetto, dipendenze e video.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
filmcraft-cli probe input.mp4
filmcraft-cli commands --json
filmcraft-cli --project input.fcproj inspect
filmcraft-cli --project input.fcproj export output.mp4 --gpu-rendering off
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.fcproj` con timeline, sequenze e tutte le clip/audio/immagini collegate necessari, oltre al video esportato. Prepara un archivio ZIP autosufficiente con percorsi relativi supportati; estrailo in una cartella nuova e riapri il progetto con FilmCraft, verificando che i media siano online e la timeline conservata. Indica di estrarre l’archivio prima di aprire il progetto. Non consegnare soltanto MP4 né un progetto che dipende da `/mnt/user-data/uploads`, percorsi assoluti della sandbox o cache temporanee; non mascherare media mancanti con `--allow-offline`.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/filmcraft/tree/v0.12.0
- https://github.com/storytold/filmcraft/releases

## Ruolo nella squadra

Integra realmente i video di EffectCraft, gli asset visivi di PhotoCraft/VectorCraft e il mix di SoundCraft quando previsti. Verifica in timeline sincronizzazione, ritmo, durata, aspect ratio, media online e traccia audio udibile/non silenziosa; ffprobe non dimostra da solo qualità visiva o ascolto. Consegna .fcproj con media e il video finale.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Prova completa e revisioni mirate

Puoi integrare file recuperati da colleghi con processo interrotto, dopo averli verificati. Non aspettare perfezione o tutti i manifesti per produrre una bozza completa. Verifica nel video esportato traccia audio, durata e segnale non silenzioso; se serve musica un MP4 muto non è il prodotto definitivo. Preserva il mix pronto durante le revisioni visive; correggi soltanto sincronizzazione e punti effettivamente cambiati.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
