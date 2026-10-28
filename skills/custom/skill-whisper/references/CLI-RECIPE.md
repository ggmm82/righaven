# Ricetta nativa: whisper.cpp

`whisper-cpp-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help whisper
craft commands whisper
craft tools whisper --out "$RIGHAVEN_OUTPUT_DIR/work/whisper-tools.json"
whisper-cpp-cli call transcribe '{"input":"/mnt/user-data/outputs/JOB/speech.wav","output":"/mnt/user-data/outputs/JOB/Sources/Transcription","language":"it"}'
```

La stessa operazione può essere invocata via `craft batch whisper` con `name` completo e `arguments` conformi allo schema MCP.

## Collaudo ripetibile

Il collaudo offline trascrive il campione parlato pubblico JFK incluso nell’upstream e verifica una parola attesa, TXT, SRT con timecode e JSON. È un controllo di funzionamento, non una misura WER su tutte le lingue. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
