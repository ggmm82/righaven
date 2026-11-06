# figcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Frame e testo con ID reali, sorgente riaperto e PNG
Lista MCP verificata per `craft batch figcraft`:
```json
[
  {"name":"run_command","arguments":{"command":"file.new"}},
  {"name":"create_node","arguments":{"type":"frame","name":"Panel","width":320,"height":180,"props":{"fill":"#ffffff"}}},
  {"name":"create_node","arguments":{"type":"text","name":"Status","text":"Contenuto verificato","parent":{"$result":"1.content.0.text.$json.id"},"x":20,"y":20,"width":280}},
  {"name":"save_file","arguments":{"path":"/mnt/user-data/outputs/figcraft/RUN/interfaccia.figcraft"}},
  {"name":"export","arguments":{"path":"/mnt/user-data/outputs/figcraft/RUN/interfaccia.png","ids":[{"$result":"1.content.0.text.$json.id"}],"format":"png"}}
]
```
Prova eseguita: frame 320×180 con testo figlio; file salvato e riaperto in una nuova sessione con `open_file` e `inspect_document`, marcatore testuale presente, PNG delle dimensioni esatte. `ids` richiede ID, non il nome «Panel». Il ritorno di `create_node` è JSON in `content[0].text`: usa `$json` per ricavarne l’ID numerico senza assumerlo. Il formato di consegna editabile verificato è `.figcraft`; `.fig` resta un export sperimentale distinto.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `figcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il progetto `.figcraft` con frame, nodi, gerarchie, testo e componenti realmente presenti, insieme agli export PNG/SVG richiesti. Riapri il file con `open_file` e `inspect_document` in una nuova sessione FigCraft e verifica testo e gerarchie. `.fig` è un export sperimentale distinto: non garantirne l’apertura in Figma o FigCraft senza una prova nella destinazione reale. Un PNG o un mockup appiattito non è un’interfaccia modificabile per componenti.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
