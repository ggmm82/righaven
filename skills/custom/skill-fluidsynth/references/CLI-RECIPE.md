# Ricetta nativa: FluidSynth

`fluidsynth-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help fluidsynth
craft commands fluidsynth
craft tools fluidsynth --out "$RIGHAVEN_OUTPUT_DIR/work/fluidsynth-tools.json"
fluidsynth-cli call render '{"input":"/mnt/user-data/outputs/JOB/score.mid","output":"/mnt/user-data/outputs/JOB/Sources/Synthesis","sample_rate":48000,"gain":0.4}'
```

La stessa operazione può essere invocata via `craft batch fluidsynth` con `name` completo e `arguments` conformi allo schema MCP.

## Collaudo ripetibile

Il collaudo sintetizza un MIDI reale, decodifica WAV stereo 48 kHz non silente e ricostruisce lo stesso audio dopo aver spostato MIDI e banca in una nuova cartella. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
