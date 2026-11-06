# Ricetta nativa: FreeCAD

`freecad-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help freecad
craft commands freecad
craft tools freecad --out "$RIGHAVEN_OUTPUT_DIR/work/freecad-tools.json"
freecad-cli call execute '{"input":"/mnt/user-data/outputs/JOB/work/build.py","output":"/mnt/user-data/outputs/JOB/Sources/CAD"}'
```

La stessa operazione può essere invocata via `craft batch freecad` con `name` completo e `arguments` conformi allo schema MCP.

Esempio minimo da adattare ai requisiti reali:

```python
import FreeCAD as App
from pathlib import Path
import os
doc = App.newDocument('Design')
box = doc.addObject('Part::Box', 'Box')
box.Length = 20; box.Width = 10; box.Height = 5
doc.recompute()
doc.saveAs(str(Path(os.environ['righaven_JOB_OUTPUT']) / 'model.FCStd'))
App.closeDocument(doc.Name)

```

## Collaudo ripetibile

Il collaudo salva e riapre un Part::Box con volume 1000 mm³, trasferisce il .FCStd, cambia Length da 20 a 30 mm, ricalcola 1500 mm³, esporta STEP e verifica il volume con il kernel nativo. Un .FCStd corrotto deve essere rifiutato. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.

La prova comprende anche un Body PartDesign con sketch rettangolare completamente vincolato, vincolo di larghezza nominato e Pad. Modifica il vincolo e verifica il ricalcolo; lo STEP deve contenere un solo solido finale, senza duplicare Body e Pad o esportare le lavorazioni intermedie.
