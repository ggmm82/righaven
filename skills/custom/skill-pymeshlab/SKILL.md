---
name: skill-pymeshlab
description: "Misura, pulizia e filtri di mesh esistenti; FreeCAD resta il CAD parametrico e Blender l’authoring organico."
---
# PyMeshLab: capacità specializzata

Misura, pulizia e filtri di mesh esistenti; FreeCAD resta il CAD parametrico e Blender l’authoring organico.

Il ruolo professionale nasce dal progetto; questa skill descrive uno strumento disponibile, non un membro obbligatorio della squadra. Eredita provider e modello della squadra. Usa solo capacità abilitate; se questo strumento è disattivato scegli un metodo diverso o dichiara il limite. Rispetta la disattivazione anche per import Python e percorsi nativi.

Prima di operare leggi [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md) e [QUALITY.md](references/QUALITY.md). Scopri gli schemi con `pymeshlab-cli commands`: non inventare nomi di operazioni. Esegui nella sandbox, conserva input e registra unità, parametri e ragioni del metodo. `pymeshlab-cli --version` controlla il runtime effettivo.

Non ricostruisce automaticamente CAD parametrico, rig o texture. L’adattatore apply produce una mesh PLY: per asset texturizzati preservare risorse e usare uno script esplicito con verifica delle UV. Un filtro registrato non è una prova di efficacia.

## Consegna: sorgenti modificabili e compatibilità

MLP, geometrie PLY/OBJ/STL, filtri MLX o Python, risorse collegate. La consegna include export separati, sorgenti completi e manuale con la sequenza realmente eseguita, versione, risorse, app di apertura e procedura di modifica. Impacchetta le dipendenze in uno ZIP portabile, estrailo in una cartella diversa e riapri il documento con l’app nativa. Non cambiare estensione per simulare compatibilità. Riporta le verifiche effettive, gli eventuali limiti e una mappa delle componenti in `delivery.components`. Un esito di processo positivo non certifica qualità professionale.
