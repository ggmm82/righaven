# Capacità operative: opentimelineio

Versione esaminata: **0.18.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Ispezione di tempi razionali, riferimenti e pacchetti media portabili; FilmCraft resta l’editor e FFmpeg il motore codec..
**Sorgenti:** Timeline OTIO e media collegati, bundle OTIOD completo dentro ZIP, script di trasformazione..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Author or transform an OTIO timeline with the native API. This is not a video editor or renderer. | `opentimelineio.execute` |
| Inspect rational timing, tracks, clips and media references in native OTIO. | `opentimelineio.inspect` |
| Check native timeline ranges and local media references. Does not decode media or certify perceptual synchronization. | `opentimelineio.check` |
| Create a portable native OTIOD bundle with media, for inclusion in a source ZIP. Reject missing or remote media. | `opentimelineio.pack` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Solo adapter core OTIO JSON/OTIOD/OTIOZ disponibili; il wrapper accetta OTIO e produce OTIOD. Nessun plugin AAF/Maya aggiuntivo. Non renderizza e non certifica sincronizzazione percettiva. Il controllo supporta riferimenti locali a file, non generatori o sequenze implicite.

## Scoperta mirata

1. `craft capabilities opentimelineio`: selezione per obiettivo e confini.
2. `craft commands opentimelineio`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools opentimelineio --out "$RIGHAVEN_OUTPUT_DIR/work/opentimelineio-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 4 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `bb53ede979142f1f05e8ccd3b92c8a28cdc850e82cd8f8799c57669f878dc19c`.
Fonte: https://opentimelineio.readthedocs.io/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
