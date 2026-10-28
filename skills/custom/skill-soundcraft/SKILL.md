---
name: skill-soundcraft
description: "Composizione MIDI, sintesi, sound design, montaggio e mix modificabile. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Produzione audio

Specialista: `soundcraft` per `harness_delegate`; nome della skill: `skill-soundcraft`.
CLI: `soundcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Composizione MIDI, sintesi, sound design, montaggio e mix modificabile. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities soundcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa SoundCraft per composizione MIDI, sintesi strumentale, sampler, sound design, montaggio, automazioni, mix e stem. Crea una sessione nativa modificabile: un WAV generato con codice non dimostra authoring SoundCraft. Il sincronismo è condiviso con animazione e montaggio: concorda cue, origine e unità, poi verifica gli eventi sul master finale.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help soundcraft` e consulta `/opt/righaven/reference/soundcraft/help.txt`.
3. Salva il registro reale con `craft commands soundcraft > "$RIGHAVEN_OUTPUT_DIR/work/soundcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools soundcraft --out "$RIGHAVEN_OUTPUT_DIR/work/soundcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch soundcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Ispeziona sample rate, canali, durata e formato delle sorgenti con ffprobe. Definisci destinazione, durata, mono/stereo, loudness e picco richiesti; non presumere un target universale.
2. Organizza tracce e tagli non distruttivi, applica dissolvenze e conserva margine di livello. Evita clipping, conversioni ripetute e normalizzazione che alteri il rapporto tra tracce senza motivo.
3. Conserva progetto multitraccia e asset mantenendo i percorsi relativi: se sposti il progetto nella cartella finale, copia anche la cartella dei media collegati (per esempio `Audio Files/`). Riapri il progetto dalla posizione di consegna e risolvi ogni avviso `missing media`. Esegui un bounce breve di prova; esporta WAV master e formati compressi richiesti con parametri espliciti.

## Diagnosi e recupero CLI

- Se la riapertura segnala missing media, verifica i percorsi dalla cartella di consegna e copia le dipendenze conservandone la struttura; il bounce non sostituisce il progetto modificabile.
- Se il master clippa o supera il target, misura il file finale e correggi livelli/processamento nella sessione. Ricalcola loudness e true peak dopo ogni nuova esportazione, senza riusare le misure di un altro file.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Con ffprobe verifica durata, sample rate, canali e codec. Controlla `ffmpeg -filters` e usa `ebur128=peak=true`, se presente, per loudness integrata e true peak sul file finale effettivo. Non equiparare picco campione e true peak e non trasferire le misure del bounce intero a un estratto. Non dichiarare assente un misuratore senza averne verificato la disponibilità.
- Controlla clipping, silenzi iniziali/finali e fade; indica separatamente ascolto reale e controlli numerici.
- Consegna progetto, mix/master ed eventuali stem; riporta target e misure senza dichiarare qualità percettiva non ascoltata.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
soundcraft-cli commands
soundcraft-cli run --demo --bounce output.wav
ffprobe -v error -show_format -show_streams -of json output.wav
ffmpeg -hide_banner -nostats -i output.wav -af ebur128=peak=true -f null -
```

## Consegna: sorgenti modificabili e compatibilità

Consegna la sessione `.scraft` con tracce, clip e impostazioni, tutti i file audio collegati (inclusa la cartella `Audio Files` se usata) e il mix/stem richiesto. Prepara un archivio autosufficiente, estrailo e riapri la sessione in SoundCraft da una cartella nuova, verificando media online, tracce, routing e durata. Spiega di estrarre prima di aprire la sessione. Il WAV/MP3 finale non conserva il montaggio multitraccia; segnala plugin, automazioni o risorse non ripristinabili.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/soundcraft/tree/v0.12.1
- https://github.com/storytold/soundcraft/releases

## Ruolo nella squadra

Prepara tracce, ritmo, mix ed effetti usando la CLI SoundCraft e una sessione multitraccia modificabile. Per video di danza concorda BPM, durata esatta e cue con EffectCraft/FilmCraft. Usa audio fornito/autorizzato o una base originale dichiarata: non promettere il brano originale da un semplice ritmo sintetico. Passa WAV/stem non silenziosi, senza clipping e con sample rate dichiarato, insieme alla sessione e ai media.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Prova completa e revisioni mirate

Per una prima bozza produci presto un loop completo breve con ritmo, basso e accenti, usando una sessione modificabile. Raggruppa la costruzione di tracce e note in batch; non comporre centinaia di note una chiamata per volta prima di verificare il primo bounce. Un master già esportato e riapribile resta utilizzabile per un’integrazione anche se la chiusura LLM fallisce. Se serve solo una piccola correzione di loudness/true peak, limita il lavoro a quella.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.

## Strumenti complementari

Per sintetizzare partiture MIDI con una banca SF2 esterna valuta `skill-fluidsynth`: conserva MIDI, banca e ricetta insieme alla sessione SoundCraft e agli stem. Per stimare attacchi, battiti e pitch usa `skill-aubio`; per conversioni e misure tecniche `skill-ffmpeg`. Questi controlli non sostituiscono ascolto, composizione, timbri adatti o mix professionale. Non importare un WAV dichiarandolo sorgente modificabile delle note.
