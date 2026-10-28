---
name: skill-aubio
description: "Stima di attacchi, battiti, altezza e note dal segnale audio, con unità esplicite. Scelta dei comandi, sorgenti e verifiche native."
---

# aubio: Analisi temporale e musicale

Versione **0.4.9**, fissata in `versions.lock.json`, con checksum verificati all’installazione. Questa skill descrive uno strumento disponibile: i ruoli si compilano dinamicamente dal progetto, senza professioni o sequenze obbligatorie. Eredita provider e modello condivisi della squadra.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md), [CAPABILITIES.md](references/CAPABILITIES.md) e [QUALITY.md](references/QUALITY.md). Usa `craft capabilities aubio`, `craft commands aubio`, `craft tools aubio` per la scoperta mirata. `aubio-cli` è l’adattatore RigHaven con CLI/MCP; gli ID MCP non sono comandi della CLI upstream. La mappa elenca le operazioni dell’adattatore, non l’intera API nativa.

## Scelta e metodo

Scegli onset per attacchi, beat per i tempi dei battiti stimati, tempo per il valore globale in BPM, pitch per segnali monofonici e notes per segmenti di nota stimati. Riporta tempi in secondi e pitch in Hz, algoritmo, sample rate e tolleranza; mantieni separata la timeline musicale da quella video. Su mix complessi controlla finestre rappresentative e confronta con eventi di riferimento osservati. Se il brano è fornito dall’utente, usa quel riferimento invece di sostituirlo con toni generici.

## Limiti verificabili

Stime del segnale, non riconoscimento della melodia, trascrizione affidabile di strumenti polifonici o giudizio musicale. Un battito stimato non prova da solo la sincronizzazione audiovisiva.

Le operazioni hanno input assoluti nel workspace, output nuovi, log e supervisione comune. Non sovrascrivere una versione approvata. Per una revisione crea una nuova consegna collegata alla precedente; descrivi il cambiamento significativo e confrontalo con il riferimento. Dopo un errore conserva log e parziali, correggi la causa e riprendi soltanto il passaggio necessario. Non duplicare processi per aggirare il budget della sandbox.

## Consegna: sorgenti modificabili e compatibilità

Conserva: Audio originale, parametri di analisi, report con unità, ricetta ripetibile; sorgenti musicali conservati dagli strumenti di authoring. Le esportazioni da sole non ricostruiscono le proprietà di authoring. Riapri o ricostruisci dopo aver trasferito sorgente e dipendenze in una cartella diversa. Distingui controllo CLI, GUI non provata e qualità percettiva non valutata.

In `handoff.json` associa ogni prodotto ai suoi sorgenti e strumenti in `delivery.components`; registra ogni file effettivo in `delivery.files` come `export`, `editable_source`, `source_archive`, `preview` o `report`, con `open_with` e `reopen` reali. Tieni log, ricevute e controlli tecnici in `work/`. Non dichiarare consegna completa se mancano risorse necessarie. Un progetto contenitore non sostituisce i sorgenti delle componenti.

## Esperienza riutilizzabile

Proponi soltanto lezioni generali sostenute da una prova: problema, metodo corretto, condizioni di applicabilità, confronto e beneficio osservato. Includi anche miglioramenti dell’uso della CLI emersi nella sandbox. Elimina nomi, percorsi e dettagli del cliente; I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non trasformare automaticamente una fixture o un fatto di progetto in una regola professionale.

## Fonte

https://aubio.org/manual/latest/cli.html
