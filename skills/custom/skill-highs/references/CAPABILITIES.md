# Capacità operative: highs

Versione esaminata: **v1.15.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Solve explicit LP and MPS optimization models.
**Sorgenti:** LP/MPS model, objective/constraints/units, solver settings, solution and native status.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Solve an explicit LP/MPS model with bounded CPU time; retain the model, native solution and log. Interpret feasibility and optimality from the report. | `highs.solve` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Distinguish optimal, feasible, infeasible, unbounded and time-limited outcomes. Never present an infeasible model or a time-limited incumbent as a proven optimum.

## Scoperta mirata

1. `craft capabilities highs`: selezione per obiettivo e confini.
2. `craft commands highs`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools highs --out "$RIGHAVEN_OUTPUT_DIR/work/highs-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `6101c5e68d821aa691aee3deed04405c1f85356a368d659f561f0683204f0512`.
Fonte: https://github.com/ERGO-Code/HiGHS. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
