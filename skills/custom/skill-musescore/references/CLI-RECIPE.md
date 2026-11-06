# Ricetta verificabile: MuseScore RigHaven

1. Leggi `musescore-cli commands` oppure `craft tools musescore` per gli schemi della versione fissata.
2. Invoca `musescore-cli call OPERAZIONE '{"input":"/mnt/user-data/...","output":"/mnt/user-data/..."}'` con i campi esatti dello schema. I nomi sono senza prefisso, per esempio `inspect`. Output sempre nuovi e separati dagli originali.
3. Usa un documento MSCZ/MusicXML/MIDI reale: questo adattatore non espone execute. Conserva la fonte musicale e crea output nuovi.
4. Controlla il documento nativo e l’export, poi ripeti la riapertura dopo aver spostato lo ZIP. Un esito negativo resta un difetto, non una consegna.
5. Compila `delivery` con artifact, editable_source, source_archive, guida d’uso e componenti effettive. Non limitarti a un file piatto.

Fonte API: https://handbook.musescore.org/command-line-usage. Prove native ripetibili: `scripts/acceptance_production.py`. La copertura è limitata alle prove eseguite, non a ogni funzione upstream.

## Procedura di composizione, non solo conversione

- Definisci melodia, metro, tempo, strumenti e forma prima del timbro. MusicXML `score-partwise` conserva altezze, durate, voci, legature e dinamiche; MIDI conserva eventi ma perde parte della notazione.
- `musescore-cli call convert '{"input":"/mnt/user-data/score.musicxml","output":"/mnt/user-data/score.mscz"}'` crea il documento nativo. `inspect` riapre la partitura e misura battute, parti e tempo; non valuta la somiglianza della melodia.
- Ripeti `convert` dal MSCZ verso `.mid`, `.pdf` e `.wav`. Il motore imposta **MuseScore Basic** per l’export offline; non richiedere download MuseSounds o login. MIDI e MSCZ accompagnano sempre una composizione nuova.
- Per un brano richiesto confronta successione e ritmo delle note con una fonte autorizzata, poi ascolta una prova. Cambiare strumento su note casuali non ricrea un brano.
- Passa MIDI e stem a SoundCraft per arrangiamento audio e mix: SoundCraft conserva il proprio `.scraft`, non sostituisce la partitura.
