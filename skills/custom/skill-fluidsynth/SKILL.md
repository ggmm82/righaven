---
name: skill-fluidsynth
description: "Rendering offline MIDI con strumenti SF2, partitura e banca conservate per la riproduzione. Scelta dei comandi, sorgenti e verifiche native."
---

# FluidSynth: Sintesi MIDI e SoundFont

Versione **2.6.1**, fissata in `versions.lock.json`, con checksum verificati all’installazione. Questa skill descrive uno strumento disponibile: i ruoli si compilano dinamicamente dal progetto, senza professioni o sequenze obbligatorie. Eredita provider e modello condivisi della squadra.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md), [CAPABILITIES.md](references/CAPABILITIES.md) e [QUALITY.md](references/QUALITY.md). Usa `craft capabilities fluidsynth`, `craft commands fluidsynth`, `craft tools fluidsynth` per la scoperta mirata. `fluidsynth-cli` è l’adattatore RigHaven con CLI/MCP; gli ID MCP non sono comandi della CLI upstream. La mappa elenca le operazioni dell’adattatore, non l’intera API nativa.

## Scelta e metodo

Conserva la partitura MIDI con tempo, programmi, canali, dinamica e articolazioni; scegli una banca coerente con il timbro richiesto. Il renderer è offline e non richiede JACK, ALSA o un dispositivo audio. Per maggiore qualità fornisci una banca SF2 autorizzata: non compensare timbri inadatti aumentando il volume. Usa SoundCraft per stem, automazioni, effetti e mix; conserva anche MIDI e banca per modificare gli strumenti, perché importare il WAV non ricrea le note nel progetto SoundCraft.

## Limiti verificabili

Sintesi MIDI con banca di campioni, non DAW multitraccia o compositore autonomo. TimGM6mb incluso è una banca General MIDI compatta: non garantisce timbri orchestrali professionali. Una registrazione WAV non conserva note modificabili.

Le operazioni hanno input assoluti nel workspace, output nuovi, log e supervisione comune. Non sovrascrivere una versione approvata. Per una revisione crea una nuova consegna collegata alla precedente; descrivi il cambiamento significativo e confrontalo con il riferimento. Dopo un errore conserva log e parziali, correggi la causa e riprendi soltanto il passaggio necessario. Non duplicare processi per aggirare il budget della sandbox.

## Consegna: sorgenti modificabili e compatibilità

Conserva: MIDI, SoundFont SF2 effettivo, licenza della banca e render-settings.json; sessione SoundCraft e stem per il mix. Le esportazioni da sole non ricostruiscono le proprietà di authoring. Riapri o ricostruisci dopo aver trasferito sorgente e dipendenze in una cartella diversa. Distingui controllo CLI, GUI non provata e qualità percettiva non valutata.

In `handoff.json` associa ogni prodotto ai suoi sorgenti e strumenti in `delivery.components`; registra ogni file effettivo in `delivery.files` come `export`, `editable_source`, `source_archive`, `preview` o `report`, con `open_with` e `reopen` reali. Tieni log, ricevute e controlli tecnici in `work/`. Non dichiarare consegna completa se mancano risorse necessarie. Un progetto contenitore non sostituisce i sorgenti delle componenti.

## Esperienza riutilizzabile

Proponi soltanto lezioni generali sostenute da una prova: problema, metodo corretto, condizioni di applicabilità, confronto e beneficio osservato. Includi anche miglioramenti dell’uso della CLI emersi nella sandbox. Elimina nomi, percorsi e dettagli del cliente; I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non trasformare automaticamente una fixture o un fatto di progetto in una regola professionale.

## Fonte

https://www.fluidsynth.org/api/fluidsynth_shell.html
