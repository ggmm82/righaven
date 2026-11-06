# Capacità operative: qgis

Versione esaminata: **3.22.16+dfsg-1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Run explicit native Processing algorithms on local geographic data.
**Sorgenti:** QGIS projects when authored, input layers/styles, parameter JSON and output layers.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run a named QGIS Processing algorithm using an explicit JSON parameter file and copied resources. Outputs must be relative to the private job folder. | `qgis.process` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

A Processing output is not automatically a complete QGIS project. Check CRS, geometry, units and relative dependencies; do not rely on unavailable plugins or external providers.

## Scoperta mirata

1. `craft capabilities qgis`: selezione per obiettivo e confini.
2. `craft commands qgis`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools qgis --out "$RIGHAVEN_OUTPUT_DIR/work/qgis-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `1a458da26856dd98ba48a083f75dee0ca3ed91610a0a18cd9bc0cc0028b2abe4`.
Fonte: https://github.com/qgis/QGIS. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
