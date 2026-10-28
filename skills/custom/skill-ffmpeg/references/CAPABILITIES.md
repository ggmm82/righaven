# Capacità operative: ffmpeg

Versione esaminata: **9.0.2**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Probe dei flussi, conversione codec e formati, estrazione audio e mux con parametri espliciti.
**Sorgenti:** Input originali, progetti delle app di authoring, media collegati, ricetta/parametri di conversione e mux.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Inspect actual streams, codecs, duration, rates and container metadata with ffprobe. | `ffmpeg.probe` |
| Create a new media export with explicit codec/rate/size. Preserve authoring projects and dependencies separately. | `ffmpeg.transcode` |
| Extract/decode audio to a new PCM16 WAV with declared sample rate and channels. | `ffmpeg.extract_audio` |
| Mux supplied video and audio from a shared zero origin; preserve video and encode AAC, without asserting sync. | `ffmpeg.mux` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Motore media, non sorgente di montaggio, compositing o composizione musicale. Un mux non prova la sincronizzazione; transcode non migliora un asset scadente. Filtri e codec upstream si scoprono con gli help nativi, il catalogo MCP espone solo le operazioni elencate.

## Scoperta mirata

1. `craft capabilities ffmpeg`: selezione per obiettivo e confini.
2. `craft commands ffmpeg`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools ffmpeg --out "$RIGHAVEN_OUTPUT_DIR/work/ffmpeg-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 4 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `bb0b9d72d9199f4b54f3012825c0b27cffd8f72a654e1779169f0404dca0134d`.
Fonte: https://ffmpeg.org/ffmpeg.html. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
