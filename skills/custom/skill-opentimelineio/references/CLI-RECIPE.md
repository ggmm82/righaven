# Ricetta verificabile: OpenTimelineIO

1. Leggi `opentimelineio-cli commands` oppure `craft tools opentimelineio` per gli schemi della versione fissata.
2. Invoca `opentimelineio-cli call OPERAZIONE '{"input":"/mnt/user-data/...","output":"/mnt/user-data/..."}'` con i campi esatti dello schema. I nomi sono senza prefisso, per esempio `execute`. Output sempre nuovi e separati dagli originali.
3. Le operazioni execute/render richiedono uno script `.py` esplicito; `resource_dir` raccoglie script e risorse relative. Non includere la directory di output fra gli input. Lo script usa `righaven_JOB_OUTPUT` per salvare i documenti.
4. Controlla il documento nativo e l’export, poi ripeti la riapertura dopo aver spostato lo ZIP. Un esito negativo resta un difetto, non una consegna.
5. Compila `delivery` con artifact, editable_source, source_archive, guida d’uso e componenti effettive. Non limitarti a un file piatto.

Fonte API: https://opentimelineio.readthedocs.io/. Prove native ripetibili: `scripts/acceptance_production.py`. La copertura è limitata alle prove eseguite, non a ogni funzione upstream.

## Tempi e media verificabili

- Usa `otio.opentime.RationalTime` e `TimeRange` per i tempi, `schema.Timeline`, `Track`, `Clip`, `ExternalReference` per il montaggio rappresentato. Definisci source_range e available_range: fotogrammi e secondi non sono intercambiabili.
- FilmCraft ha già `file.exportOtio` e `file.exportInterchange`: prima esporta la timeline esistente, poi usa `opentimelineio-cli call check` per range e riferimenti. Non ricreare un montaggio che l’editor già conserva.
- `execute` permette trasformazioni esplicite con l’API Python. Salva tramite `adapters.write_to_file`; gli adapter core disponibili sono `otio_json`, `otiod`, `otioz`, non AAF/FCP di terze parti.
- `pack` riceve `.otio`, rifiuta file mancanti/remoti e genera `Timeline.otiod/content.otio` con `media`. I nomi includono hash per evitare collisioni di basename. Consegna l’intera cartella in uno ZIP e verifica di nuovo `content.otio` dopo lo spostamento, con gli originali indisponibili.
- La verifica non decodifica i flussi. Usa FFprobe per durate/fps e una prova audio-video per sincronia reale; transizioni e timewarp richiedono un controllo nel renderer di destinazione.
