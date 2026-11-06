# Ricetta nativa: Typst

`typst-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help typst
craft commands typst
craft tools typst --out "$RIGHAVEN_OUTPUT_DIR/work/typst-tools.json"
typst-cli call compile '{"input":"/mnt/user-data/outputs/JOB/Sources/main.typ","output":"/mnt/user-data/outputs/JOB/book.pdf","resource_dir":"/mnt/user-data/outputs/JOB/Sources"}'
```

La stessa operazione può essere invocata via `craft batch typst` con `name` completo e `arguments` conformi allo schema MCP.

Esempio minimo da adattare ai requisiti reali:

```typst
#set page(paper: "a4", margin: 22mm)
#set text(font: "DejaVu Sans", lang: "it")
= Titolo
Contenuto strutturato e modificabile.

```

## Collaudo ripetibile

Il collaudo compila .typ in PDF e PNG, estrae testo dal PDF, sposta e modifica la sorgente e ricompila. Un sorgente con funzione inesistente deve fallire. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
