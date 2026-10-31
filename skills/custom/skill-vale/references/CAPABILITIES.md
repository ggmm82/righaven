# Capacità operative: vale

Versione esaminata: **v3.24.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Check prose against style rules (Vale built-in rules or a supplied .vale.ini with local styles); save JSON alerts.
**Sorgenti:** Text, .vale.ini with styles and JSON alerts.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Check prose against style rules (Vale built-in rules or a supplied .vale.ini with local styles); save JSON alerts. | `vale.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Rules check style mechanically; they do not judge content, tone or accuracy.

## Scoperta mirata

1. `craft capabilities vale`: selezione per obiettivo e confini.
2. `craft commands vale`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools vale --out "$RIGHAVEN_OUTPUT_DIR/work/vale-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `e71c0d21b114f4e7f957cd5cf910e1fdd1d33c5714de39e605a7268816f24ece`.
Fonte: https://github.com/errata-ai/vale. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
