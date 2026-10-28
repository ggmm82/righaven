# Ricetta nativa: aubio

`aubio-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help aubio
craft commands aubio
craft tools aubio --out "$RIGHAVEN_OUTPUT_DIR/work/aubio-tools.json"
aubio-cli call analyze '{"input":"/mnt/user-data/outputs/JOB/audio.wav","output":"/mnt/user-data/outputs/JOB/work/onsets.json","feature":"onset"}'
```

La stessa operazione può essere invocata via `craft batch aubio` con `name` completo e `arguments` conformi allo schema MCP.

## Collaudo ripetibile

Il collaudo misura un segnale reale a 440 Hz, verifica la tolleranza del pitch e rileva gli attacchi di impulsi temporizzati. Beat e note sono eseguiti nativamente ma non certificati esatti per musica reale. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
