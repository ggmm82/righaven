# Capacità operative: abcmidi

Versione esaminata: **20230208**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Convert ABC music notation into a MIDI file for listening checks.
**Sorgenti:** ABC source and MIDI file.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Convert ABC music notation into a MIDI file for listening checks. | `abcmidi.midi` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

MIDI playback uses default instruments and tempo; it is a listening check, not a final mix.

## Scoperta mirata

1. `craft capabilities abcmidi`: selezione per obiettivo e confini.
2. `craft commands abcmidi`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools abcmidi --out "$RIGHAVEN_OUTPUT_DIR/work/abcmidi-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `8ee9ee155f8c4ac6ec83f701ccd8abd0dc58cc2739993a475831864341e1f260`.
Fonte: https://github.com/sshlien/abcmidi. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
