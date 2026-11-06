# Capacità operative: tflint

Versione esaminata: **v0.64.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Lint a Terraform module directory with the bundled core rules (no provider plugins downloaded); save JSON findings.
**Sorgenti:** Module folder and JSON findings.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Lint a Terraform module directory with the bundled core rules (no provider plugins downloaded); save JSON findings. | `tflint.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Only bundled core rules run offline; provider-specific rules and real plans need the provider plugins and credentials.

## Scoperta mirata

1. `craft capabilities tflint`: selezione per obiettivo e confini.
2. `craft commands tflint`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools tflint --out "$RIGHAVEN_OUTPUT_DIR/work/tflint-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `eca81d705354b9339257b6bcf03d7ac138eceedaa5a7d166f51c039320af8631`.
Fonte: https://github.com/terraform-linters/tflint. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
