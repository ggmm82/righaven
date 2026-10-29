# Capacità operative: axe-core

Versione esaminata: **4.14.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Inspect actual browser pages for axe accessibility rules.
**Sorgenti:** Page or application sources, audit URL/state, native JSON findings and incomplete checks.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run axe-core in real headless Chromium on an authorized page; report violations, incomplete checks and limits. | `axe-core.audit` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Complements Playwright behavior tests. Zero violations does not certify WCAG compliance; keyboard, screen-reader and human review remain necessary.

## Scoperta mirata

1. `craft capabilities axe-core`: selezione per obiettivo e confini.
2. `craft commands axe-core`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools axe-core --out "$RIGHAVEN_OUTPUT_DIR/work/axe-core-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `551e84c4716012db5815b9157d58cfc7507e2b9abf08a27b35a7a03cb28f8602`.
Fonte: https://github.com/dequelabs/axe-core. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
