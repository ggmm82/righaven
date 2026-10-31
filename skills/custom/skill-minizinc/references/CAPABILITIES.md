# Capacità operative: minizinc

Versione esaminata: **2.6.4**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Solve a MiniZinc constraint model (optionally with a .dzn data file) using Gecode within a time limit; save every printed solution and the optimality status.
**Sorgenti:** Model, data file and printed solutions with status.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Solve a MiniZinc constraint model (optionally with a .dzn data file) using Gecode within a time limit; save every printed solution and the optimality status. | `minizinc.solve` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

A time limit may stop before optimality; only ========== marks a proven optimum for the encoded model.

## Scoperta mirata

1. `craft capabilities minizinc`: selezione per obiettivo e confini.
2. `craft commands minizinc`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools minizinc --out "$RIGHAVEN_OUTPUT_DIR/work/minizinc-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `892384029fe8a9f33849ac5449a7d6c0a5a78da4ff466dbadc5fd84474498e5e`.
Fonte: https://github.com/MiniZinc/libminizinc. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
