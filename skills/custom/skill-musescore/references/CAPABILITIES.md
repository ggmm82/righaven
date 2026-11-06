# Capacità operative: musescore

Versione esaminata: **v4.7.5**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Partiture, arrangiamenti e melodia esplicita; SoundCraft resta responsabile del mix..
**Sorgenti:** MSCZ, MusicXML, MIDI, risorse e indicazioni di tempo; WAV/MP3 sono export..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Reopen a score in MuseScore and read native score metadata. | `musescore.inspect` |
| Export a score with offline MuseScore Basic sounds. Preserve MSCZ/MusicXML as editable sources; audio is an export. | `musescore.convert` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Non sostituisce il montaggio o il mix SoundCraft. Il banco offline MuseScore Basic non è MuseSounds. La presenza di note non prova somiglianza musicale o qualità percettiva.

## Scoperta mirata

1. `craft capabilities musescore`: selezione per obiettivo e confini.
2. `craft commands musescore`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools musescore --out "$RIGHAVEN_OUTPUT_DIR/work/musescore-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `0699b019a14705339dc1d8536ec1ab48e56cb86d85e64072813c5081c05a5d65`.
Fonte: https://handbook.musescore.org/command-line-usage. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
