# Capacità operative: zint

Versione esaminata: **2.11.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Encode data as a barcode or 2D code (QR, Data Matrix, PDF417, Code 128, EAN-13, GS1-128) in SVG or PNG; check scannability on the final medium.
**Sorgenti:** Encoded data file and SVG/PNG code.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Encode data as a barcode or 2D code (QR, Data Matrix, PDF417, Code 128, EAN-13, GS1-128) in SVG or PNG; check scannability on the final medium. | `zint.encode` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Generation is not a scan test; check size, quiet zone and contrast on the final printed medium.

## Scoperta mirata

1. `craft capabilities zint`: selezione per obiettivo e confini.
2. `craft commands zint`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools zint --out "$RIGHAVEN_OUTPUT_DIR/work/zint-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `3c15c8e939dac065cadb8088dc71df01bf9e28589468101684a4543c0dd05085`.
Fonte: https://github.com/zint/zint. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
