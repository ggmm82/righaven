# Capacità operative: k6

Versione esaminata: **v2.3.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Run explicit small load tests with thresholds and native metric summaries.
**Sorgenti:** JavaScript scenario, fixtures, thresholds, target configuration and metric summary.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Execute an explicit local load-test script with bounded iterations and virtual users against an authorized test system. | `k6.run` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Select test traffic and authorization before running. Bound VUs, iterations and duration. Report actual load and latency percentiles; a local sample is not a production capacity guarantee.

## Scoperta mirata

1. `craft capabilities k6`: selezione per obiettivo e confini.
2. `craft commands k6`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools k6 --out "$RIGHAVEN_OUTPUT_DIR/work/k6-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `1b721e3c160a656cb5dfbfa5d5eaf4f63b046877593880960c5620b0e01f4381`.
Fonte: https://github.com/grafana/k6. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
