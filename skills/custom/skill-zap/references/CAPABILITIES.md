# Capacità operative: zap

Versione esaminata: **v2.17.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Spider an authorized application and collect passive security findings with an explicit automation plan.
**Sorgenti:** Authorization/scope, automation plan, native XML report and reproduction guidance.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run ZAP Quick Start without an active attack against an explicitly authorized URL. Save native XML evidence; passive findings are not a complete penetration test. | `zap.baseline` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

The adapter contains no activeScan job. Spidering still sends requests and can affect poorly designed applications. Keep target scope narrow, triage findings and distinguish an incomplete scan from no findings.

## Scoperta mirata

1. `craft capabilities zap`: selezione per obiettivo e confini.
2. `craft commands zap`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools zap --out "$RIGHAVEN_OUTPUT_DIR/work/zap-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `5e81e6f2aa8ad4d2995f90d1222dc6dde06fbeff36cada7bbb59ef41500dbac1`.
Fonte: https://github.com/zaproxy/zaproxy. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
