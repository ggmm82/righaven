# Capacità operative: quarto

Versione esaminata: **1.10.19**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Publish analytical narratives and notebooks as standalone HTML reports.
**Sorgenti:** QMD, notebooks, local assets, configuration and rendered report.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Render a copied QMD project to standalone HTML using local resources. PDF requires a separately selected engine. | `quarto.render` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Use Quarto for executable reports, Typst for typography and Pandoc for conversion. The adapter produces HTML; PDF engines, extensions and publishing services are not silently installed.

## Scoperta mirata

1. `craft capabilities quarto`: selezione per obiettivo e confini.
2. `craft commands quarto`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools quarto --out "$RIGHAVEN_OUTPUT_DIR/work/quarto-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `1194824fb09949d0a20fbfb285e34840f02647eeb4d0de73e434392c7bad7ce8`.
Fonte: https://github.com/quarto-dev/quarto-cli. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
