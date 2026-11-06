---
name: skill-freecad
description: "Authoring parametrico .FCStd, misure geometriche e scambio STEP tramite motore headless nativo. Scelta dei comandi, sorgenti e verifiche native."
---

# FreeCAD: CAD parametrico tridimensionale

Versione **1.1.4**, fissata in `versions.lock.json`, con checksum verificati all’installazione. Questa skill descrive uno strumento disponibile: i ruoli si compilano dinamicamente dal progetto, senza professioni o sequenze obbligatorie. Eredita provider e modello condivisi della squadra.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md), [CAPABILITIES.md](references/CAPABILITIES.md) e [QUALITY.md](references/QUALITY.md). Usa `craft capabilities freecad`, `craft commands freecad`, `craft tools freecad` per la scoperta mirata. `freecad-cli` è l’adattatore RigHaven con CLI/MCP; gli ID MCP non sono comandi della CLI upstream. La mappa elenca le operazioni dell’adattatore, non l’intera API nativa.

## Scelta e metodo

Usa oggetti parametrici, sketch/vincoli e dipendenze quando il progetto richiede modifiche dimensionali; non consegnare una sola mesh triangolata dichiarandola CAD parametrico. Gli script .py possono importare FreeCAD e Part; righaven_JOB_OUTPUT indica la nuova cartella assegnata. Salva .FCStd, chiudi il documento e riaprilo in un processo distinto. Controlla unità in mm, volumi, validità dei solidi, tolleranze e ricalcolo dopo la modifica di una quota. Usa Blender per rendering/animazione e CADCraft per tavole 2D se pertinenti; non confondere i formati di authoring.

## Limiti verificabili

Motore headless FreeCAD 1.1.4 dalla distribuzione ufficiale, con il Python incluso. Verifica le API contro questa versione. STEP conserva geometria di scambio, non lo storico parametrico .FCStd; nessuna certificazione ingegneristica o prova GUI implicita.

Le operazioni hanno input assoluti nel workspace, output nuovi, log e supervisione comune. Non sovrascrivere una versione approvata. Per una revisione crea una nuova consegna collegata alla precedente; descrivi il cambiamento significativo e confrontalo con il riferimento. Dopo un errore conserva log e parziali, correggi la causa e riprendi soltanto il passaggio necessario. Non duplicare processi per aggirare il budget della sandbox.

## Consegna: sorgenti modificabili e compatibilità

Conserva: Documento nativo .FCStd con albero parametrico, script .py realmente usato, dati e riferimenti; STEP come export di scambio. Le esportazioni da sole non ricostruiscono le proprietà di authoring. Riapri o ricostruisci dopo aver trasferito sorgente e dipendenze in una cartella diversa. Distingui controllo CLI, GUI non provata e qualità percettiva non valutata.

In `handoff.json` associa ogni prodotto ai suoi sorgenti e strumenti in `delivery.components`; registra ogni file effettivo in `delivery.files` come `export`, `editable_source`, `source_archive`, `preview` o `report`, con `open_with` e `reopen` reali. Tieni log, ricevute e controlli tecnici in `work/`. Non dichiarare consegna completa se mancano risorse necessarie. Un progetto contenitore non sostituisce i sorgenti delle componenti.

## Esperienza riutilizzabile

Proponi soltanto lezioni generali sostenute da una prova: problema, metodo corretto, condizioni di applicabilità, confronto e beneficio osservato. Includi anche miglioramenti dell’uso della CLI emersi nella sandbox. Elimina nomi, percorsi e dettagli del cliente; I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non trasformare automaticamente una fixture o un fatto di progetto in una regola professionale.

## Fonte

https://freecad.github.io/SourceDoc/
