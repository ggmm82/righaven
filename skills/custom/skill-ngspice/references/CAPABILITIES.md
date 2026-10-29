# Capacità operative: ngspice

Versione esaminata: **39.3+ds-1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Simulate explicit SPICE netlists and preserve actual raw results.
**Sorgenti:** Netlist, included component models, stimuli, analysis settings and raw simulation data.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run a local SPICE netlist in batch mode, preserving models, netlist and native results. | `ngspice.simulate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Check model licenses, convergence, units and operating conditions. Simulation does not guarantee physical performance or safety; preserve all local include files.

## Scoperta mirata

1. `craft capabilities ngspice`: selezione per obiettivo e confini.
2. `craft commands ngspice`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools ngspice --out "$RIGHAVEN_OUTPUT_DIR/work/ngspice-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `39e8dfe1ff0030e4603c19b9805c4fbae53d829429c243e6d7cc5714c27612e2`.
Fonte: https://ngspice.sourceforge.io. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
