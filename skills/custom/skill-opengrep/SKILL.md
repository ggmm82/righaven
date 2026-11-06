---
name: skill-opengrep
description: "Analisi statica di codice con regole YAML locali esplicite. Evidenze ripetibili, limiti e sorgenti conservati."
---
# opengrep

Versione v1.32.0, fissata con checksum. Questa è una competenza di strumento: il ruolo professionale dipende dal progetto. Usa provider e modello centralizzati della squadra.

Leggi skill-workspace e [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), [QUALITY.md](references/QUALITY.md). Scopri gli schemi con `craft tools opengrep` e `craft commands opengrep`; `opengrep-cli` è un adattatore, non l’intera CLI upstream.

Analisi statica di codice con regole YAML locali esplicite. Limita il perimetro ai file e target autorizzati. Nessuna esecuzione del codice esaminato. I finding richiedono triage; zero finding non significa sicurezza garantita. Non inventare vulnerabilità. Non usare il tool per attacchi. Richiede regole YAML locali; non scarica regole remote automaticamente.

## Consegna: sorgenti modificabili e compatibilità

Conserva Codice o configurazione esaminati, regole locali, report JSON, scan-recipe.json e metadata del database quando usato. Consegna finding con posizione, prova, gravità motivata e correzione verificata. Mantieni separati errore di scansione, rischio confermato e limite del controllo. Registra i file di report in delivery.files e i sorgenti pertinenti in delivery.components; non sostituire il sorgente con una schermata. Verifica il report riaprendolo, senza eseguire il codice sotto esame.

Proponi lezioni generali sostenute da confronto e prova. category=tool_operation richiede il test automatico documentato in skill-workspace; category=production_method richiede accettazione dell’utente. Elimina dettagli del cliente, segreti e percorsi specifici.

Fonte: https://github.com/opengrep/opengrep
