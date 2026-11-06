# Capacità operative: soundcraft

Versione esaminata: **v0.12.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Composizione MIDI, sintesi, sound design, montaggio e mix modificabile.
**Sorgenti:** .scraft con strumenti/note, clip, automazioni, media, stem e mix.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Strumenti e tracce | `engine.plugins`, `track.new`, `mix.instrument`, `mix.instrument_param`, `mix.sampler_load` |
| Composizione MIDI | `midi.new_clip`, `midi.note_add`, `midi.note_edit`, `midi.notes_move`, `event.quantize`, `file.import_midi` |
| Tempo, cue e montaggio | `event.tempo`, `markers.add`, `clip.place_source`, `clip.identify_sync_point`, `clip.conform_to_tempo` |
| Mix, effetti e automazioni | `mix.volume`, `mix.pan`, `mix.insert`, `mix.insert_param`, `mix.send`, `automation.set_point` |
| Sessione, stem e master | `session.save`, `file.bounce_mix`, `file.bounce_stems`, `file.export_midi` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sono presenti sintetizzatore sottrattivo, drum synth e sampler, non solo importazione WAV. Non è un servizio che genera canzoni finite da una frase. CLI --start/--end in secondi; bounce_mix MCP in campioni; MIDI in tick. Non confondere unità o disponibilità GUI con funzioni headless.

## Scoperta mirata

1. `craft capabilities soundcraft`: selezione per obiettivo e confini.
2. `craft commands soundcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools soundcraft --out "$RIGHAVEN_OUTPUT_DIR/work/soundcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 480 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `6febba88d4a0362184fa6acead566ab571531bf6dc552a7f3637c0b7ab043afe`.
Fonte: https://github.com/storytold/soundcraft/tree/v0.7.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
