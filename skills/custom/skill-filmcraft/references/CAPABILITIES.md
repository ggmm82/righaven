# Capacità operative: filmcraft

Versione esaminata: **v0.12.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Montaggio, sequenze, composizione di contributi, colore e master audiovisivo.
**Sorgenti:** .fcproj, media e pacchetto portabile; master separato.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Sequenze e montaggio | `file.newSequence`, `timeline.place`, `timeline.move`, `source.insert`, `source.overwrite` |
| Tagli, velocità e transizioni | `timeline.razor`, `timeline.trim`, `timeline.slip`, `clip.speedDuration`, `sequence.setTransition`, `sequence.applyVideoTransition` |
| Audio, mixer e sincronismo | `clip.synchronize`, `clip.audioGain`, `clip.audioChannels`, `mixer.addInsert`, `mixer.setInsert`, `markers.exportCsv` |
| Titoli e sottotitoli | `captions.newTrack`, `captions.add`, `captions.setStyle`, `captions.export` |
| Scambio, relink e consegna | `media.relink`, `media.autoRelink`, `file.exportMedia`, `file.exportOtio`, `file.exportFcp7Xml`, `file.exportAaf` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Monta e tratta media; non implica generazione di scene, musica o ripristino dei sorgenti degli ingredienti. Compatibilità della GUI separata dal render CLI.

## Scoperta mirata

1. `craft capabilities filmcraft`: selezione per obiettivo e confini.
2. `craft commands filmcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools filmcraft --out "$RIGHAVEN_OUTPUT_DIR/work/filmcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 701 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `776fc8a8b45fd1073aacb4f30ec13cb642b141569ad1db76ed16c498ea97aa19`.
Fonte: https://github.com/storytold/filmcraft/tree/v0.7.2. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
