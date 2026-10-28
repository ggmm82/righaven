# soundcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Importazione audio, sessione e bounce con intervallo esatto
Lista MCP verificata per `craft batch soundcraft`:
```json
[
  {"name":"new_session","arguments":{"name":"Mix","template":"blank","sample_rate":48000}},
  {"name":"import_audio","arguments":{"path":"/mnt/user-data/uploads/sorgente.wav"}},
  {"name":"save_session","arguments":{"path":"/mnt/user-data/outputs/soundcraft/RUN/sessione.scraft"}},
  {"name":"bounce_mix","arguments":{"path":"/mnt/user-data/outputs/soundcraft/RUN/mix.wav","start":0,"end":24000,"bit_depth":"16","format":"wav"}}
]
```
Prova eseguita: sorgente WAV mono di 0,5 secondi → sessione nativa → mix stereo PCM16 a 48 kHz di 0,5 secondi, picco non nullo e sotto clipping. **Gli intervalli numerici di questo tool sono campioni, non secondi:** a 48 kHz `end=24000` significa 0,5 secondi; `end=0.5` ha prodotto soltanto un campione. Calcola l’intervallo dal sample rate reale. Riapri la sessione dalla cartella di consegna e verifica anche `Audio Files/sorgente.wav`. La prova è numerica, non un ascolto; misura loudness e true peak sul mix reale quando richiesti.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `soundcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna la sessione `.scraft` con tracce, clip e impostazioni, tutti i file audio collegati (inclusa la cartella `Audio Files` se usata) e il mix/stem richiesto. Prepara un archivio autosufficiente, estrailo e riapri la sessione in SoundCraft da una cartella nuova, verificando media online, tracce, routing e durata. Spiega di estrarre prima di aprire la sessione. Il WAV/MP3 finale non conserva il montaggio multitraccia; segnala plugin, automazioni o risorse non ripristinabili.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.

## Composizione MIDI e sintetizzatore nativo: prova aggiuntiva

Provati nella 0.7.0: `subtractive_synth`, clip MIDI con tre note, bounce non silenzioso, salvataggio `.scraft`, copia del solo sorgente in altra cartella e nuovo bounce. Non richiede importare un WAV. Sono inoltre elencati `drum_synth` e `sampler`: verificarne preset, parametri e resa per l’incarico, senza attribuire loro il collaudo del sintetizzatore sottrattivo.

```bash
soundcraft-cli plugins
soundcraft-cli run --cmd 'session.new={"name":"Prova nativa","sample_rate":48000}' --cmd 'track.new={"kind":"instrument","instrument":"subtractive_synth","name":"Lead"}' --save "$RIGHAVEN_OUTPUT_DIR/sessione.scraft"
```

Leggi l’ID effettivo in `tracks[0].id` del file salvato, quindi esegui `midi.new_clip={"track":ID_REALE,"start":0,"end":96000}` in un `run --in` e salva una nuova versione. Recupera il nuovo ID della clip da `tracks[0].playlists[0].clips[0].id`. Aggiungi note con `midi.note_add={"clip":ID_REALE,"pitch":60,"start_ticks":0,"length_ticks":480,"velocity":90}` e salva `.scraft` prima del bounce. Non incollare `ID_REALE` come stringa né assumere gli ID dell’esempio.

**Unità distinte:** clip start/end in campioni; MIDI start_ticks/length_ticks in tick; `soundcraft-cli run --bounce ... --start 0 --end 2` in secondi; MCP `bounce_mix.end` in campioni. Leggi tempo, risoluzione MIDI e sample rate della sessione prima della conversione. Nella prova 96.000 campioni a 48 kHz sono due secondi; `--end 96000` nel CLI bounce non significa due secondi.

Prova automatizzata completa: `/opt/righaven/check_tool_capabilities.py --soundcraft-authoring`. Controlla tre note persistenti, plugin nativo, assenza di sorgente audio importato, durata/sample rate/canali e bounce non nullo anche dopo trasferimento. Non è un ascolto né un esempio di composizione professionale. Per il brief reale servono orchestrazione/sound design, livelli, accenti e revisione pertinenti; preserva parametri, sessione e stem.
