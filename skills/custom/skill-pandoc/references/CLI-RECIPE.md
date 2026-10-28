# Ricetta nativa: Pandoc

`pandoc-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help pandoc
craft commands pandoc
craft tools pandoc --out "$RIGHAVEN_OUTPUT_DIR/work/pandoc-tools.json"
pandoc-cli call convert '{"input":"/mnt/user-data/outputs/JOB/Sources/source.md","output":"/mnt/user-data/outputs/JOB/book.docx","standalone":true}'
```

La stessa operazione può essere invocata via `craft batch pandoc` con `name` completo e `arguments` conformi allo schema MCP.

## Collaudo ripetibile

Il collaudo converte Markdown in DOCX ed EPUB, controlla il testo nei contenitori e riapre DOCX in Markdown. Il round-trip di un campione non certifica ogni funzione di tutti i formati. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
