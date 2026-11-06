---
name: skill-ifcopenshell
description: "Authoring semantico BIM e validazione IFC; FreeCAD resta il modellatore CAD parametrico."
---
# IfcOpenShell: capacità specializzata

Authoring semantico BIM e validazione IFC; FreeCAD resta il modellatore CAD parametrico.

Il ruolo professionale nasce dal progetto; questa skill descrive uno strumento disponibile, non un membro obbligatorio della squadra. Eredita provider e modello della squadra. Usa solo capacità abilitate; se questo strumento è disattivato scegli un metodo diverso o dichiara il limite. Rispetta la disattivazione anche per import Python e percorsi nativi.

Prima di operare leggi [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md) e [QUALITY.md](references/QUALITY.md). Scopri gli schemi con `ifcopenshell-cli commands`: non inventare nomi di operazioni. Esegui nella sandbox, conserva input e registra unità, parametri e ragioni del metodo. `ifcopenshell-cli --version` controlla il runtime effettivo.

La validazione dello schema non certifica geometria, normativa o sicurezza strutturale. Non richiede Blender e non ricostruisce uno storico CAD da una mesh.

## Consegna: sorgenti modificabili e compatibilità

IFC, script Python, unità, proprietà e risorse originali. La consegna include export separati, sorgenti completi e manuale con la sequenza realmente eseguita, versione, risorse, app di apertura e procedura di modifica. Impacchetta le dipendenze in uno ZIP portabile, estrailo in una cartella diversa e riapri il documento con l’app nativa. Non cambiare estensione per simulare compatibilità. Riporta le verifiche effettive, gli eventuali limiti e una mappa delle componenti in `delivery.components`. Un esito di processo positivo non certifica qualità professionale.
