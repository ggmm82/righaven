# Ricetta CLI: D2

1. Scegli la notazione per il problema e conserva la fonte del brief. Compila uno schema corto e leggibile.
2. `d2-cli commands` o `craft tools d2` descrive i parametri reali. Usa `d2-cli call render '{"input":"/mnt/user-data/model.d2","output":"/mnt/user-data/outputs/design"}'`. Output sempre nuovo; gli originali sono preservati.
3. Correggi errori e riferimenti mancanti prima di estendere lo schema. Mantieni la semantica nel sorgente, lo stile negli export.
4. Sposta i sorgenti e ripeti il controllo nativo. Il collaudo ripetibile è in `scripts/acceptance_design.py`.
5. In `delivery` separa modello modificabile, SVG/PNG/PDF, ZIP e manuale. Registra le scelte, non ragionamenti privati.

Documentazione ufficiale: https://d2lang.com.

## Grammatica e metodo

Usa `direction: right`, nodi `idea: Idea`, connessioni `idea -> risultato: relazione`, contenitori con `{ ... }`, `shape: diamond` per decisioni e `shape: sequence_diagram` quando serve una sequenza. Mantieni una relazione per riga e ID brevi stabili; separa la descrizione dalla chiave. Le gerarchie raggruppano componenti, non impongono fasi di esecuzione.

`d2-cli call render` accetta `layout: "elk"` o `"dagre"`; il wrapper chiama davvero `d2 validate` e poi il renderer SVG con asset incorporati. L’adattatore espone SVG: per una consegna PDF/PNG usa una capacità di esportazione pertinente già abilitata. Gli altri formati supportati upstream non sono tutti coperti dall’adattatore.

Confronta i due layout se incroci o lunghezza delle etichette rendono difficile la lettura. Nessuna freccia senza un significato dichiarato. Conserva il `.d2` come fonte logica anche dopo una rifinitura grafica del SVG.
