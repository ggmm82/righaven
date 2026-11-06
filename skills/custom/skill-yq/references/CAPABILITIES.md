# Capacità operative: yq

Versione esaminata: **3.1.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Apply a jq filter to YAML (or XML/TOML read as YAML) and save YAML output.
**Sorgenti:** Input YAML, filter and YAML result.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Apply a jq filter to YAML (or XML/TOML read as YAML) and save YAML output. | `yq.transform` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Comments and anchors are not preserved by the jq round trip; keep the original as the editable source.

## Scoperta mirata

1. `craft capabilities yq`: selezione per obiettivo e confini.
2. `craft commands yq`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools yq --out "$RIGHAVEN_OUTPUT_DIR/work/yq-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `31f5ecabc1a96231a3a7cd38ee4ff1660ef520ef8be7994d83b14023bd1fde6e`.
Fonte: https://github.com/kislyuk/yq. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
