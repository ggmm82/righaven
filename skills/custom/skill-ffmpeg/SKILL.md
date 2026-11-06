---
name: skill-ffmpeg
description: "Conversione, filtri, mux e verifiche tecniche audio/video; scelta rispetto alle app di authoring, sorgenti e sincronizzazione."
---

# FFmpeg: conformazione, conversione e controllo dei media

FFmpeg **9.0.2**, compilato dal tag upstream ufficiale con SHA-256 fissato nel catalogo. Era già disponibile come dipendenza del runtime; ora ha una skill e un adattatore CLI/MCP espliciti. Eredita il modello della squadra; non definisce un ruolo professionale fisso.

Leggi `skill-workspace`, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), [QUALITY.md](references/QUALITY.md). `ffmpeg-cli` è l’adattatore RigHaven; `ffmpeg` e `ffprobe` sono i binari upstream. Scopri prima `craft capabilities ffmpeg`, `craft commands ffmpeg`, `craft tools ffmpeg`.

## Scelta del metodo e sovrapposizioni

Usa FFmpeg per ispezione di stream, codec/container, frame rate, sample rate, estrazione audio, conversione e mux finale. Usa FilmCraft per il montaggio modificabile, EffectCraft per compositing/animazioni, SoundCraft per mix e automazioni, FluidSynth per partitura MIDI con SF2. FFmpeg può svolgere lavorazioni avanzate ma non ricrea automaticamente i progetti nativi di queste app: non sceglierlo per aggirare i sorgenti richiesti.

Il catalogo MCP copre probe, transcode, extract_audio e mux; per filtri avanzati consulta `ffmpeg -filters`, `ffmpeg -h filter=NOME`, `ffmpeg -encoders`, `ffmpeg -h encoder=NOME` e `ffmpeg -h full`. Supervisiona anche i comandi nativi lunghi. Evita opzioni inventate, combinazioni codec/container incompatibili e processi concorrenti nel budget del worker.

`ffmpeg.probe` salva JSON con stream reali. `transcode` crea un nuovo file con codec, fps, dimensioni e taglio espliciti; copy non può cambiare dimensione/fps. `extract_audio` produce PCM16 WAV con rate/canali dichiarati. `mux` associa il video fornito e l’audio fornito con origine comune zero, copia il video e codifica AAC: non corregge offset, non allunga silenziosamente una traccia e non certifica il sync. Se le durate differiscono scegli esplicitamente taglio, silenzio o altro raccordo in base al brief.

## Sincronizzazione e qualità

Prima del mux verifica timeline, timebase, origine, durata e eventi significativi condivisi. Mantieni i timecode dei segmenti, non usare la semplice uguaglianza delle durate come prova di sync. Dopo il mux confronta eventi audio/video in più punti e controlla drift, clipping, loudness, colori, aspect ratio e codec compatibili con la destinazione. Misure e decodifica non equivalgono a visione o ascolto del prodotto.

## Consegna: sorgenti modificabili e compatibilità

Consegna i media richiesti con i progetti di authoring realmente usati, media collegati, originali pertinenti e ricetta/parametri riproducibili. Un comando FFmpeg o un WAV/MP4 non sostituisce il progetto FilmCraft/SoundCraft/EffectCraft quando quei contenuti sono stati creati lì. Per la sola conversione di un originale fornito conserva originale e ricetta, senza inventare una sessione nativa mai usata.

In `handoff.json` registra `delivery.files` e associa prodotti/sorgenti in `delivery.components` agli strumenti reali, con `open_with` e `reopen` verificati. Report e ricevute restano in `work/`. Distingui qualità percettiva non osservata e controlli tecnici eseguiti. Riapri/rigenera una copia dopo trasferimento del pacchetto completo.

Proponi lezioni generali sull’uso migliore dei filtri e dei parametri solo con prova e beneficio osservato; nessuna attivazione senza accettazione della singola lezione.

Fonte: https://ffmpeg.org/documentation.html
