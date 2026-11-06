# Capacità operative: jupyter

Versione esaminata: **6.5.3-3**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Combine explanations, executable Python and actual analytical results in a notebook.
**Sorgenti:** Input and executed IPYNB, datasets, environment requirements and figures.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Execute a notebook in a copied resource folder with a bounded cell timeout; retain input and executed notebooks. | `jupyter.execute` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Execute in a fresh kernel, in order. Clear stale outputs; preserve random seeds, dependencies and data provenance. Notebook execution is code execution, not a web notebook service.

## Scoperta mirata

1. `craft capabilities jupyter`: selezione per obiettivo e confini.
2. `craft commands jupyter`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools jupyter --out "$RIGHAVEN_OUTPUT_DIR/work/jupyter-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `9e6c42753d2123b1589633f15a8cca347e15f65f20458e76d22c3f0e27b566c3`.
Fonte: https://github.com/jupyter/nbconvert. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
