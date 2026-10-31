# Capacità operative: ajv

Versione esaminata: **5.0.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Validate JSON data against a JSON Schema (draft 2020-12, 2019-09 or 07) and save all errors.
**Sorgenti:** Data, schema and validation errors.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Validate JSON data against a JSON Schema (draft 2020-12, 2019-09 or 07) and save all errors. | `ajv.validate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Schema validity covers structure and declared formats only, not business rules outside the schema.

## Scoperta mirata

1. `craft capabilities ajv`: selezione per obiettivo e confini.
2. `craft commands ajv`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools ajv --out "$RIGHAVEN_OUTPUT_DIR/work/ajv-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `e5cfc4771ed1948515656be81a1488ff2335d9cc7593efe0ca4066116c00d83b`.
Fonte: https://github.com/ajv-validator/ajv-cli. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
