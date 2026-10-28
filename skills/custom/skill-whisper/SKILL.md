---
name: skill-whisper
description: "Trascrizione parlato CPU multilingue in TXT, SRT e JSON con modello tiny fissato e disponibile offline. Scelta dei comandi, sorgenti e verifiche native."
---

# whisper.cpp: Trascrizione e sottotitoli

Versione **v1.9.5**, fissata in `versions.lock.json`, con checksum verificati all’installazione. Questa skill descrive uno strumento disponibile: i ruoli si compilano dinamicamente dal progetto, senza professioni o sequenze obbligatorie. Eredita provider e modello condivisi della squadra.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md), [CAPABILITIES.md](references/CAPABILITIES.md) e [QUALITY.md](references/QUALITY.md). Usa `craft capabilities whisper`, `craft commands whisper`, `craft tools whisper` per la scoperta mirata. `whisper-cpp-cli` è l’adattatore RigHaven con CLI/MCP; gli ID MCP non sono comandi della CLI upstream. La mappa elenca le operazioni dell’adattatore, non l’intera API nativa.

## Scelta e metodo

Il modello tiny è già installato con hash e revisione fissati: nessun download durante il job. L’adattatore decodifica audio mono PCM16 a 16 kHz e usa due thread CPU. Scegli la lingua se nota, controlla segmenti e tempi contro l’originale, annota incertezze e revisiona nomi/termini specialistici. Usa i sottotitoli con l’editor video mantenendo la stessa origine temporale; evita di trascrivere una canzone per provarne la correttezza musicale. In un progetto lungo lavora su segmenti espliciti senza perdere offset e raccordi.

## Limiti verificabili

Riconoscimento del parlato CPU con tiny multilingue: può sbagliare nomi, numeri e lingue e inventare testo nel rumore o nella musica. Non riconosce una melodia e non equivale ad ascolto percettivo o valutazione del mix.

Le operazioni hanno input assoluti nel workspace, output nuovi, log e supervisione comune. Non sovrascrivere una versione approvata. Per una revisione crea una nuova consegna collegata alla precedente; descrivi il cambiamento significativo e confrontalo con il riferimento. Dopo un errore conserva log e parziali, correggi la causa e riprendi soltanto il passaggio necessario. Non duplicare processi per aggirare il budget della sandbox.

## Consegna: sorgenti modificabili e compatibilità

Conserva: Audio originale o riferimento autorizzato, TXT/SRT/JSON modificabili, lingua e configurazione, identificativo e hash del modello. Le esportazioni da sole non ricostruiscono le proprietà di authoring. Riapri o ricostruisci dopo aver trasferito sorgente e dipendenze in una cartella diversa. Distingui controllo CLI, GUI non provata e qualità percettiva non valutata.

In `handoff.json` associa ogni prodotto ai suoi sorgenti e strumenti in `delivery.components`; registra ogni file effettivo in `delivery.files` come `export`, `editable_source`, `source_archive`, `preview` o `report`, con `open_with` e `reopen` reali. Tieni log, ricevute e controlli tecnici in `work/`. Non dichiarare consegna completa se mancano risorse necessarie. Un progetto contenitore non sostituisce i sorgenti delle componenti.

## Esperienza riutilizzabile

Proponi soltanto lezioni generali sostenute da una prova: problema, metodo corretto, condizioni di applicabilità, confronto e beneficio osservato. Includi anche miglioramenti dell’uso della CLI emersi nella sandbox. Elimina nomi, percorsi e dettagli del cliente; I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non trasformare automaticamente una fixture o un fatto di progetto in una regola professionale.

## Fonte

https://github.com/ggml-org/whisper.cpp
