# Capacità operative: shellcheck

Versione esaminata: **0.9.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Analyze a shell script for bugs and portability issues; save JSON findings.
**Sorgenti:** Script and JSON findings.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Analyze a shell script for bugs and portability issues; save JSON findings. No finding does not prove the script is correct. | `shellcheck.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

No finding does not prove correctness; behaviour still needs tests on the target shell and system.

## Scoperta mirata

1. `craft capabilities shellcheck`: selezione per obiettivo e confini.
2. `craft commands shellcheck`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools shellcheck --out "$RIGHAVEN_OUTPUT_DIR/work/shellcheck-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `8c4c960f18892855bda06abaf2c03af875302f7a7db0e04b19e9ddd53b2ab176`.
Fonte: https://github.com/koalaman/shellcheck. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
