# Capacità operative: typst

Versione esaminata: **v0.15.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Composizione tipografica riproducibile in PDF, SVG o PNG da sorgenti .typ, font e risorse.
**Sorgenti:** Sorgenti .typ, template e moduli locali, dati, immagini, font e ricetta di compilazione.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Compile a local .typ source into PDF, SVG or PNG with explicit resource root. Does not certify print readiness. | `typst.compile` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Motore tipografico programmabile, non un editor grafico WYSIWYG o garanzia di PDF/X, CMYK, accessibilità o conformità di stampa. Pacchetti e font devono essere disponibili e versionati; non presupporre download in un worker offline.

## Scoperta mirata

1. `craft capabilities typst`: selezione per obiettivo e confini.
2. `craft commands typst`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools typst --out "$RIGHAVEN_OUTPUT_DIR/work/typst-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `0a7f891aaeb164d02b3bd296a0fbbc1730c9fbb10b0a6ba2d899fcdcf702ab90`.
Fonte: https://typst.app/docs/reference/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
