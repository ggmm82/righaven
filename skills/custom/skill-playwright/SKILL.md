---
name: skill-playwright
description: "Automazione browser, test di interazione, screenshot e trace su applicazioni web reali. Scelta dei comandi, sorgenti e verifiche native."
---

# Playwright: Collaudo browser e interfacce

Versione **1.64.1**, fissata in `versions.lock.json`, con checksum verificati all’installazione. Questa skill descrive uno strumento disponibile: i ruoli si compilano dinamicamente dal progetto, senza professioni o sequenze obbligatorie. Eredita provider e modello condivisi della squadra.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md), [CAPABILITIES.md](references/CAPABILITIES.md) e [QUALITY.md](references/QUALITY.md). Usa `craft capabilities playwright`, `craft commands playwright`, `craft tools playwright` per la scoperta mirata. `playwright-cli` è l’adattatore RigHaven con CLI/MCP; gli ID MCP non sono comandi della CLI upstream. La mappa elenca le operazioni dell’adattatore, non l’intera API nativa.

## Scelta e metodo

Scegli i percorsi critici del progetto e scrivi asserzioni su effetti osservabili: stato salvato, contenuto, errori, navigazione, permessi e viewport. Evita pause arbitrarie, selettori fragili e screenshot senza asserzioni. Per pagine protette usa un account di prova autorizzato e conserva sessioni/token fuori dalla consegna. Il test deve fallire se il requisito viene violato. Chromium è già installato: non scaricare browser durante il lavoro.

## Limiti verificabili

Collaudo reale Chromium headless CPU; non certifica tutti i browser, accessibilità o qualità visiva. Non vede automaticamente servizi interni: verifica URL e autenticazione. Gli script sono codice eseguito dentro la sandbox, non nel Gateway.

Le operazioni hanno input assoluti nel workspace, output nuovi, log e supervisione comune. Non sovrascrivere una versione approvata. Per una revisione crea una nuova consegna collegata alla precedente; descrivi il cambiamento significativo e confrontalo con il riferimento. Dopo un errore conserva log e parziali, correggi la causa e riprendi soltanto il passaggio necessario. Non duplicare processi per aggirare il budget della sandbox.

## Consegna: sorgenti modificabili e compatibilità

Conserva: Codice applicativo, test .test.cjs o automazione .cjs, configurazione, screenshot e trace pertinenti. Le esportazioni da sole non ricostruiscono le proprietà di authoring. Riapri o ricostruisci dopo aver trasferito sorgente e dipendenze in una cartella diversa. Distingui controllo CLI, GUI non provata e qualità percettiva non valutata.

In `handoff.json` associa ogni prodotto ai suoi sorgenti e strumenti in `delivery.components`; registra ogni file effettivo in `delivery.files` come `export`, `editable_source`, `source_archive`, `preview` o `report`, con `open_with` e `reopen` reali. Tieni log, ricevute e controlli tecnici in `work/`. Non dichiarare consegna completa se mancano risorse necessarie. Un progetto contenitore non sostituisce i sorgenti delle componenti.

## Esperienza riutilizzabile

Proponi soltanto lezioni generali sostenute da una prova: problema, metodo corretto, condizioni di applicabilità, confronto e beneficio osservato. Includi anche miglioramenti dell’uso della CLI emersi nella sandbox. Elimina nomi, percorsi e dettagli del cliente; I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non trasformare automaticamente una fixture o un fatto di progetto in una regola professionale.

## Fonte

https://playwright.dev/docs/test-cli
