# Capacità operative: actionlint

Versione esaminata: **v1.7.11**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Check a GitHub Actions workflow: syntax, expressions, job dependencies and embedded scripts; save JSON findings.
**Sorgenti:** Workflow file and JSON findings.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Check a GitHub Actions workflow: syntax, expressions, job dependencies and embedded scripts; save JSON findings. | `actionlint.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Static checks cannot prove secrets, permissions or runners behave as intended at run time.

## Scoperta mirata

1. `craft capabilities actionlint`: selezione per obiettivo e confini.
2. `craft commands actionlint`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools actionlint --out "$RIGHAVEN_OUTPUT_DIR/work/actionlint-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `ec0e1c0dd6ea226ec09c60e2f25378c363356744cdc87316c3fd8af90265070e`.
Fonte: https://github.com/rhysd/actionlint. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
