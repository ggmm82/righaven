# Capacità operative: fluidsynth

Versione esaminata: **2.6.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Rendering offline MIDI con strumenti SF2, partitura e banca conservate per la riproduzione.
**Sorgenti:** MIDI, SoundFont SF2 effettivo, licenza della banca e render-settings.json; sessione SoundCraft e stem per il mix.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Offline MIDI + SF2 synthesis into a new portable folder: WAV, MIDI, bank and render settings. No audio device. | `fluidsynth.render` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sintesi MIDI con banca di campioni, non DAW multitraccia o compositore autonomo. TimGM6mb incluso è una banca General MIDI compatta: non garantisce timbri orchestrali professionali. Una registrazione WAV non conserva note modificabili.

## Scoperta mirata

1. `craft capabilities fluidsynth`: selezione per obiettivo e confini.
2. `craft commands fluidsynth`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools fluidsynth --out "$RIGHAVEN_OUTPUT_DIR/work/fluidsynth-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `152c39608a9e6cb0390c86e159536199ad52df4d52a4fd829dd79588f376eb40`.
Fonte: https://www.fluidsynth.org/api/fluidsynth_shell.html. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
