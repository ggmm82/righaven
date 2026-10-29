# Capacità operative: openmodelica

Versione esaminata: **1.27.1~2-g6db4671-1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Compile and simulate explicit Modelica models and MOS recipes on CPU.
**Sorgenti:** MO models, MOS recipe, parameters, local libraries, units and simulation data.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Execute an explicit MOS recipe in a copied project folder; retain Modelica models, parameters and simulation results. | `openmodelica.simulate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Do not silently download libraries. Use explicit initial conditions and solver settings, check actual simulation success and numerical plausibility. This is not engineering certification.

## Scoperta mirata

1. `craft capabilities openmodelica`: selezione per obiettivo e confini.
2. `craft commands openmodelica`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools openmodelica --out "$RIGHAVEN_OUTPUT_DIR/work/openmodelica-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `5a2d3d7e78563ba1670119dd40836acf87d84cdbcc1b0a9a3ee591c347fee83e`.
Fonte: https://github.com/OpenModelica/OpenModelica. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
