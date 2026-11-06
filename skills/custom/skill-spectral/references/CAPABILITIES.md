# Capacità operative: spectral

Versione esaminata: **6.17.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Lint an OpenAPI or AsyncAPI document with the standard Spectral rulesets or a supplied ruleset; save JSON findings.
**Sorgenti:** API document, ruleset and JSON findings.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Lint an OpenAPI or AsyncAPI document with the standard Spectral rulesets or a supplied ruleset; save JSON findings. | `spectral.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

A clean lint is not a working API; test the implementation against the contract separately.

## Scoperta mirata

1. `craft capabilities spectral`: selezione per obiettivo e confini.
2. `craft commands spectral`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools spectral --out "$RIGHAVEN_OUTPUT_DIR/work/spectral-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `606e2cccdc9e2117dc87eac482864a5b8b6f178bd84e45b4fbd58c6f584dc4fe`.
Fonte: https://github.com/stoplightio/spectral. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
