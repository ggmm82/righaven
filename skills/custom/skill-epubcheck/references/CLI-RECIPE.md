# Ricetta nativa: EPUBCheck

`epubcheck-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help epubcheck
craft commands epubcheck
craft tools epubcheck --out "$RIGHAVEN_OUTPUT_DIR/work/epubcheck-tools.json"
epubcheck-cli call check '{"input":"/mnt/user-data/outputs/JOB/book.epub","output":"/mnt/user-data/outputs/JOB/work/epubcheck.json"}'
```

La stessa operazione può essere invocata via `craft batch epubcheck` con `name` completo e `arguments` conformi allo schema MCP.

## Collaudo ripetibile

Il collaudo valida un EPUB realmente creato da Pandoc e deve rifiutare una copia ZIP valida da cui è stato rimosso un capitolo ancora referenziato. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
