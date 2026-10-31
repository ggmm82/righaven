# Capacità operative: fonttools

Versione esaminata: **4.38.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** List the OpenType tables of a font file with their checksums and sizes.
**Sorgenti:** Original font, subset font and table listing.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| List the OpenType tables of a font file with their checksums and sizes. | `fonttools.inspect` |
| Subset a font to the characters of a given text and save TTF, WOFF or WOFF2; licences must allow subsetting. | `fonttools.subset` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Subsetting must be allowed by the font licence; check rendering of every required language after subsetting.

## Scoperta mirata

1. `craft capabilities fonttools`: selezione per obiettivo e confini.
2. `craft commands fonttools`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools fonttools --out "$RIGHAVEN_OUTPUT_DIR/work/fonttools-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `b95a894453722b7e3f75602b3dcaed393f3a0c899ec69ccbcd67fb62de489691`.
Fonte: https://github.com/fonttools/fonttools. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
