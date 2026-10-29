# Capacità operative: schemathesis

Versione esaminata: **4.32.7**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Exercise authorized test APIs against a saved OpenAPI contract.
**Sorgenti:** Original OpenAPI schema, target configuration, native JUnit report and reproducible test parameters.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Exercise an explicitly authorized HTTP API from a local OpenAPI schema. Save native JUnit evidence; may create or modify test data. | `schemathesis.test` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Requests may mutate data. Use an authorized disposable target, bound examples and workers, and preserve failing cases. Passing schema checks do not prove business correctness.

## Scoperta mirata

1. `craft capabilities schemathesis`: selezione per obiettivo e confini.
2. `craft commands schemathesis`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools schemathesis --out "$RIGHAVEN_OUTPUT_DIR/work/schemathesis-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `d6d5e2df41d5897ba0ebcf782a0cac83f6818eeff0b147cdabd81f4568d0ac9f`.
Fonte: https://github.com/schemathesis/schemathesis. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
