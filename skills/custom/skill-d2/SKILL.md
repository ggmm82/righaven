---
name: skill-d2
description: "Flussi, relazioni e dipendenze con layout automatico; non richiede UML o professioni fisse."
---
# D2: progettazione modificabile

Flussi, relazioni e dipendenze con layout automatico; non richiede UML o professioni fisse.

Il ruolo si compila dal progetto. Usa questa capacità quando aiuta a chiarire risultato, alternative, relazioni o vincoli; non imporre un diagramma o una fase preliminare a ogni incarico. Eredita modello e provider della squadra. Rispetta le disattivazioni anche per API e percorsi nativi.

Leggi `references/CAPABILITIES.md`, `references/CLI-RECIPE.md` e `references/QUALITY.md`. Usa `d2-cli commands` per gli schemi reali. Conserva gli ID logici e collega, quando utile, nodi a ruoli, attività, criteri e consegne del progetto. Lo schema illustra e verifica il progetto: non sostituisce il risultato richiesto.

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief.

## Consegna: sorgenti modificabili e compatibilità

D2 .d2 autonomo e ricetta; SVG/PNG/PDF come export. Includi il sorgente reale, ricetta, app/versione di apertura e guida alle modifiche. Consegna lo ZIP con sorgenti e risorse quando esistono più file. Riapri o rigenera da una copia spostata; dichiara le prove effettive. Non chiamare modificabile un PNG o un PDF privo del modello. Compila `delivery.components` con i sorgenti della stessa versione.
