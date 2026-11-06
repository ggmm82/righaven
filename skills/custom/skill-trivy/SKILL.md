---
name: skill-trivy
description: "Controllo configurazioni, inventario CycloneDX e vulnerabilità con database esplicito. Evidenze ripetibili, limiti e sorgenti conservati."
---
# trivy

Versione v0.76.1, fissata con checksum. Questa è una competenza di strumento: il ruolo professionale dipende dal progetto. Usa provider e modello centralizzati della squadra.

Leggi skill-workspace e [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), [QUALITY.md](references/QUALITY.md). Scopri gli schemi con `craft tools trivy` e `craft commands trivy`; `trivy-cli` è un adattatore, non l’intera CLI upstream.

Controllo configurazioni, inventario CycloneDX e vulnerabilità con database esplicito. Limita il perimetro ai file e target autorizzati. Nessuna esecuzione del codice esaminato. I finding richiedono triage; zero finding non significa sicurezza garantita. Non inventare vulnerabilità. Non usare il tool per attacchi. Config usa controlli incorporati. SBOM non equivale a vulnerability scan. Vulnerabilities richiede database aggiornato esplicitamente con database_update: l’assenza del DB è un errore, mai zero finding.

## Consegna: sorgenti modificabili e compatibilità

Conserva Codice o configurazione esaminati, regole locali, report JSON, scan-recipe.json e metadata del database quando usato. Consegna finding con posizione, prova, gravità motivata e correzione verificata. Mantieni separati errore di scansione, rischio confermato e limite del controllo. Registra i file di report in delivery.files e i sorgenti pertinenti in delivery.components; non sostituire il sorgente con una schermata. Verifica il report riaprendolo, senza eseguire il codice sotto esame.

Proponi lezioni generali sostenute da confronto e prova. category=tool_operation richiede il test automatico documentato in skill-workspace; category=production_method richiede accettazione dell’utente. Elimina dettagli del cliente, segreti e percorsi specifici.

Fonte: https://github.com/aquasecurity/trivy
