---
name: skill-musescore
description: "Partiture, arrangiamenti e melodia esplicita; SoundCraft resta responsabile del mix."
---
# MuseScore RigHaven: capacità specializzata

Partiture, arrangiamenti e melodia esplicita; SoundCraft resta responsabile del mix.

Il ruolo professionale nasce dal progetto; questa skill descrive uno strumento disponibile, non un membro obbligatorio della squadra. Eredita provider e modello della squadra. Usa solo capacità abilitate; se questo strumento è disattivato scegli un metodo diverso o dichiara il limite. Rispetta la disattivazione anche per import Python e percorsi nativi.

Prima di operare leggi [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md) e [QUALITY.md](references/QUALITY.md). Scopri gli schemi con `musescore-cli commands`: non inventare nomi di operazioni. Esegui nella sandbox, conserva input e registra unità, parametri e ragioni del metodo. `musescore-cli --version` controlla il runtime effettivo.

Non sostituisce il montaggio o il mix SoundCraft. Il banco offline MuseScore Basic non è MuseSounds. La presenza di note non prova somiglianza musicale o qualità percettiva.

## Consegna: sorgenti modificabili e compatibilità

MSCZ, MusicXML, MIDI, risorse e indicazioni di tempo; WAV/MP3 sono export. La consegna include export separati, sorgenti completi e manuale con la sequenza realmente eseguita, versione, risorse, app di apertura e procedura di modifica. Impacchetta le dipendenze in uno ZIP portabile, estrailo in una cartella diversa e riapri il documento con l’app nativa. Non cambiare estensione per simulare compatibilità. Riporta le verifiche effettive, gli eventuali limiti e una mappa delle componenti in `delivery.components`. Un esito di processo positivo non certifica qualità professionale.
