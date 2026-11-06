# Capacità operative: whisper

Versione esaminata: **v1.9.5**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Trascrizione parlato CPU multilingue in TXT, SRT e JSON con modello tiny fissato e disponibile offline.
**Sorgenti:** Audio originale o riferimento autorizzato, TXT/SRT/JSON modificabili, lingua e configurazione, identificativo e hash del modello.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| CPU speech transcription into TXT/SRT/JSON with pinned multilingual tiny model. Does not assess music or speaker identity. | `whisper.transcribe` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Riconoscimento del parlato CPU con tiny multilingue: può sbagliare nomi, numeri e lingue e inventare testo nel rumore o nella musica. Non riconosce una melodia e non equivale ad ascolto percettivo o valutazione del mix.

## Scoperta mirata

1. `craft capabilities whisper`: selezione per obiettivo e confini.
2. `craft commands whisper`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools whisper --out "$RIGHAVEN_OUTPUT_DIR/work/whisper-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `238253cca6185b3d88cdf04e72ad9f7e17f4a0c61ef47f2f62b691894914d8b7`.
Fonte: https://github.com/ggml-org/whisper.cpp. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
