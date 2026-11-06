# effectcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Composizione con keyframe, sorgente riaperto e GIF
Per un progetto nuovo, la CLI dispone del motore JavaScript AE-style:
```bash
effectcraft-cli --empty --save-as "$RIGHAVEN_OUTPUT_DIR/animazione.ecproj" script --eval 'var c=app.project.items.addComp("Main",160,90,1,0.6,10); var l=c.layers.addSolid([0.2,0.5,1],"Box",30,30,1); l.property("Transform").property("Position").setValueAtTime(0,[30,45]); l.property("Transform").property("Position").setValueAtTime(0.5,[120,45]);'
effectcraft-cli --project "$RIGHAVEN_OUTPUT_DIR/animazione.ecproj" info
effectcraft-cli --project "$RIGHAVEN_OUTPUT_DIR/animazione.ecproj" render-frame --comp Main --time 0 --out "$RIGHAVEN_OUTPUT_DIR/previews/prima.png" --transparent
effectcraft-cli --project "$RIGHAVEN_OUTPUT_DIR/animazione.ecproj" render --comp Main --out "$RIGHAVEN_OUTPUT_DIR/animazione.gif" --format gif --start 0 --end 0.6 --fps 10
```
Prova eseguita: sorgente modificabile, frame a 0 e 0,5 secondi diversi con alpha, GIF di sei fotogrammi. Le misure, durate e colori sono dimostrativi: adatta al brief. I tempi qui sono secondi. Il percorso del progetto è un’opzione `--project`, non un argomento posizionale finale di `render` o `info`. Per MCP usa i tool pubblicati: non aggirare le restrizioni degli script del server.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `effectcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il progetto `.ecproj`, le risorse collegate necessarie e gli export richiesti (GIF/video/frame). Riapri con `effectcraft-cli --project ... info` e verifica composizioni, livelli e keyframe, non soltanto un frame renderizzato. Per media esterni prepara e prova un pacchetto autosufficiente estratto in una nuova cartella. Un video/GIF non conserva di per sé livelli o keyframe modificabili; registra font, plugin o effetti non disponibili.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.

## Correggere un progetto esistente senza perdere le modifiche

Le modifiche richiedono salvataggio esplicito e riapertura in un processo nuovo:

```bash
effectcraft-cli --project "$RIGHAVEN_OUTPUT_DIR/animazione.ecproj" --save script --eval 'app.project.item(1).layer(1).property("Transform").property("Opacity").setValue(0);'
effectcraft-cli --project "$RIGHAVEN_OUTPUT_DIR/animazione.ecproj" render-frame --comp Main --time 0 --out "$RIGHAVEN_OUTPUT_DIR/previews/revisione.png" --transparent
```

È un test di persistenza sulla fixture sopra: il livello diventa trasparente dopo riapertura. Nel prodotto reale seleziona composizione, oggetto e proprietà effettivi; conserva la baseline con `--save-as` quando serve. Verifica una proprietà modificata o il fotogramma del difetto prima del render completo: un hash diverso da solo non dimostra che la modifica richiesta sia persistita.
