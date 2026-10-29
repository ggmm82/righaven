# Capacità operative: prusaslicer

Versione esaminata: **2.5.0+dfsg-4**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Slice existing models using explicit printer and material settings.
**Sorgenti:** Original mesh or 3MF project, printer/material INI, slicing recipe and G-code.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Slice a local mesh using an explicit printer/material configuration; preserve model, configuration and G-code. Does not certify printer safety. | `prusaslicer.slice` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Do not replace CAD/mesh authoring tools. G-code is machine-specific; confirm printer, bed, nozzle, temperatures, supports and scale before use. Do not claim a physical print was tested.

## Scoperta mirata

1. `craft capabilities prusaslicer`: selezione per obiettivo e confini.
2. `craft commands prusaslicer`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools prusaslicer --out "$RIGHAVEN_OUTPUT_DIR/work/prusaslicer-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `ed3506f7e2fe040d55edf841c589562d8f8aded9fb69eb06c8f34a025e66f0af`.
Fonte: https://github.com/prusa3d/PrusaSlicer. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
