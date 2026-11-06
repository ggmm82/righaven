---
name: skill-bpmn
description: "Processi con eventi, responsabilità, decisioni ed eccezioni in BPMN 2.0; non è un nuovo esecutore dei lavori."
---
# BPMN / bpmn.io: progettazione modificabile

Processi con eventi, responsabilità, decisioni ed eccezioni in BPMN 2.0; non è un nuovo esecutore dei lavori.

Il ruolo si compila dal progetto. Usa questa capacità quando aiuta a chiarire risultato, alternative, relazioni o vincoli; non imporre un diagramma o una fase preliminare a ogni incarico. Eredita modello e provider della squadra. Rispetta le disattivazioni anche per API e percorsi nativi.

Leggi `references/CAPABILITIES.md`, `references/CLI-RECIPE.md` e `references/QUALITY.md`. Usa `bpmn-cli commands` per gli schemi reali. Conserva gli ID logici e collega, quando utile, nodi a ruoli, attività, criteri e consegne del progetto. Lo schema illustra e verifica il progetto: non sostituisce il risultato richiesto.

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief. Il file deve contenere il layout BPMN DI. Le segnalazioni di importazione vanno corrette, non ignorate.

## Consegna: sorgenti modificabili e compatibilità

BPMN .bpmn con DI e riferimenti coerenti; SVG/PNG/PDF come export. Includi il sorgente reale, ricetta, app/versione di apertura e guida alle modifiche. Consegna lo ZIP con sorgenti e risorse quando esistono più file. Riapri o rigenera da una copia spostata; dichiara le prove effettive. Non chiamare modificabile un PNG o un PDF privo del modello. Compila `delivery.components` con i sorgenti della stessa versione.
