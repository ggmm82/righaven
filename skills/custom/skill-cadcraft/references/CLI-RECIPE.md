# cadcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Rettangolo metrico modificabile e verifica geometrica
```bash
cadcraft-cli run --metric --cmd 'units {"insunits":4}' --cmd 'pline {"vertices":[[0,0],[40,0],[40,20],[0,20]],"closed":true}' --save "$RIGHAVEN_OUTPUT_DIR/rettangolo.dxf"
cadcraft-cli info "$RIGHAVEN_OUTPUT_DIR/rettangolo.dxf"
cadcraft-cli convert "$RIGHAVEN_OUTPUT_DIR/rettangolo.dxf" "$RIGHAVEN_OUTPUT_DIR/previews/rettangolo.svg"
```
Prova eseguita: un rettangolo di 40×20 mm. Il test legge direttamente i gruppi DXF: quattro vertici `LWPOLYLINE`, flag di chiusura, coordinate e `$INSUNITS=4` (millimetri), poi riapre il file e valida l’SVG. Adatta dimensioni e tolleranze al brief; la scala di stampa è distinta dalle unità del modello.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `cadcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il disegno DXF modificabile verificato con CADCraft, conservando layer, entità, unità e quote realmente supportate; DXF è il formato operativo verificato, non inventare un’estensione proprietaria. Riaprilo con `cadcraft-cli info` e una nuova sessione `cadcraft-cli run`, poi confronta entità e misure. Un GLB/GLTF o un viewer HTML è un export 3D, non la prova di un documento apribile in CADCraft. La ricetta collaudata copre DXF 2D: non promettere import GLB o modellazione parametrica/3D senza verificarli nella release reale. Se il brief richiede 3D e il registro non lo supporta, dichiara il limite al coordinatore; non sostituire il modello richiesto con una sagoma 2D, non rinominare GLB in DXF e non usare la sola validazione GLB come verifica CADCraft.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
