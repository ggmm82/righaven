---
name: skill-structurizr
description: "Viste coerenti di architettura software da un unico modello C4. Usa le librerie mantenute, non la vecchia CLI dismessa."
---
# Structurizr DSL: progettazione modificabile

Viste coerenti di architettura software da un unico modello C4. Usa le librerie mantenute, non la vecchia CLI dismessa.

Il ruolo si compila dal progetto. Usa questa capacità quando aiuta a chiarire risultato, alternative, relazioni o vincoli; non imporre un diagramma o una fase preliminare a ogni incarico. Eredita modello e provider della squadra. Rispetta le disattivazioni anche per API e percorsi nativi.

Leggi `references/CAPABILITIES.md`, `references/CLI-RECIPE.md` e `references/QUALITY.md`. Usa `structurizr-cli commands` per gli schemi reali. Conserva gli ID logici e collega, quando utile, nodi a ruoli, attività, criteri e consegne del progetto. Lo schema illustra e verifica il progetto: non sostituisce il risultato richiesto.

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief. Modalità ristretta delle librerie DSL 6.2.3, Java 21 isolato; nessun server o servizio enterprise. Export testuali, non un renderer aggiuntivo.

## Consegna: sorgenti modificabili e compatibilità

DSL .dsl, workspace JSON ed export PlantUML/Mermaid; eventuali immagini sono del renderer scelto. Includi il sorgente reale, ricetta, app/versione di apertura e guida alle modifiche. Consegna lo ZIP con sorgenti e risorse quando esistono più file. Riapri o rigenera da una copia spostata; dichiara le prove effettive. Non chiamare modificabile un PNG o un PDF privo del modello. Compila `delivery.components` con i sorgenti della stessa versione.
