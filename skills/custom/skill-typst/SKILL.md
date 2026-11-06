---
name: skill-typst
description: "Composizione tipografica riproducibile in PDF, SVG o PNG da sorgenti .typ, font e risorse. Scelta dei comandi, sorgenti e verifiche native."
---

# Typst: Impaginazione programmabile

Versione **v0.15.1**, fissata in `versions.lock.json`, con checksum verificati all’installazione. Questa skill descrive uno strumento disponibile: i ruoli si compilano dinamicamente dal progetto, senza professioni o sequenze obbligatorie. Eredita provider e modello condivisi della squadra.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md), [CAPABILITIES.md](references/CAPABILITIES.md) e [QUALITY.md](references/QUALITY.md). Usa `craft capabilities typst`, `craft commands typst`, `craft tools typst` per la scoperta mirata. `typst-cli` è l’adattatore RigHaven con CLI/MCP; gli ID MCP non sono comandi della CLI upstream. La mappa elenca le operazioni dell’adattatore, non l’intera API nativa.

## Scelta e metodo

Progetta griglia, margini, gerarchie, stili, numerazione, riferimenti e gestione di tabelle/figure prima di espandere tutte le pagine. Valida pagine rappresentative con contenuti difficili, glifi italiani e cambi pagina. Usa root esplicito per asset relativi e font locali con licenza; conserva i moduli/pacchetti necessari. Riduci il perimetro prima della finitura e verifica che le revisioni non introducano overflow, vedove o riferimenti errati.

## Limiti verificabili

Motore tipografico programmabile, non un editor grafico WYSIWYG o garanzia di PDF/X, CMYK, accessibilità o conformità di stampa. Pacchetti e font devono essere disponibili e versionati; non presupporre download in un worker offline.

Le operazioni hanno input assoluti nel workspace, output nuovi, log e supervisione comune. Non sovrascrivere una versione approvata. Per una revisione crea una nuova consegna collegata alla precedente; descrivi il cambiamento significativo e confrontalo con il riferimento. Dopo un errore conserva log e parziali, correggi la causa e riprendi soltanto il passaggio necessario. Non duplicare processi per aggirare il budget della sandbox.

## Consegna: sorgenti modificabili e compatibilità

Conserva: Sorgenti .typ, template e moduli locali, dati, immagini, font e ricetta di compilazione. Le esportazioni da sole non ricostruiscono le proprietà di authoring. Riapri o ricostruisci dopo aver trasferito sorgente e dipendenze in una cartella diversa. Distingui controllo CLI, GUI non provata e qualità percettiva non valutata.

In `handoff.json` associa ogni prodotto ai suoi sorgenti e strumenti in `delivery.components`; registra ogni file effettivo in `delivery.files` come `export`, `editable_source`, `source_archive`, `preview` o `report`, con `open_with` e `reopen` reali. Tieni log, ricevute e controlli tecnici in `work/`. Non dichiarare consegna completa se mancano risorse necessarie. Un progetto contenitore non sostituisce i sorgenti delle componenti.

## Esperienza riutilizzabile

Proponi soltanto lezioni generali sostenute da una prova: problema, metodo corretto, condizioni di applicabilità, confronto e beneficio osservato. Includi anche miglioramenti dell’uso della CLI emersi nella sandbox. Elimina nomi, percorsi e dettagli del cliente; I metodi di realizzazione (category=production_method) richiedono accettazione dell’utente. Le conoscenze operative delle CLI (category=tool_operation) si attivano dopo il test automatico documentato in skill-workspace; senza prova restano inattive nella sezione tecnica, senza chiedere approvazione all’utente. Non trasformare automaticamente una fixture o un fatto di progetto in una regola professionale.

## Fonte

https://typst.app/docs/reference/


## Confine fra modelli e impaginazione

Typst può disegnare schemi semplici, ma la consegna PDF non autorizza a sostituire modelli di architettura, processi, dati o disegni tecnici con forme decorative. Quando il mandato richiede quella semantica, integra gli export dagli strumenti di modellazione assegnati e conserva i loro sorgenti. Se il ruolo non dispone delle capacità necessarie, segnala il limite al coordinatore prima di semplificare il prodotto. Non usare C4/BPMN per ogni illustrazione: scegli in base al significato richiesto.
