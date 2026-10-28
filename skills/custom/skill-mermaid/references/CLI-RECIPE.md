# Ricetta CLI: Mermaid

1. Scegli la notazione per il problema e conserva la fonte del brief. Compila uno schema corto e leggibile.
2. `mermaid-cli commands` o `craft tools mermaid` descrive i parametri reali. Usa `mermaid-cli call render '{"input":"/mnt/user-data/model.mmd","output":"/mnt/user-data/outputs/design"}'`. Output sempre nuovo; gli originali sono preservati.
3. Correggi errori e riferimenti mancanti prima di estendere lo schema. Mantieni la semantica nel sorgente, lo stile negli export.
4. Sposta i sorgenti e ripeti il controllo nativo. Il collaudo ripetibile è in `scripts/acceptance_design.py`.
5. In `delivery` separa modello modificabile, SVG/PNG/PDF, ZIP e manuale. Registra le scelte, non ragionamenti privati.

Documentazione ufficiale: https://mermaid.js.org.

## Diagrammi nella chat e nel Markdown

Usa `flowchart LR` o `TD` per flussi, `sequenceDiagram` per messaggi, `stateDiagram-v2` per stati, `classDiagram` per classi; mindmap, Gantt ed ER quando pertinenti. Quota etichette con spazi e simboli, evita ID ambigui e controlla il diagramma nel parser della versione installata.

Il frontend RigHaven visualizza già i blocchi `mermaid`: usa quello per la discussione. La capacità CLI produce file `.mmd`, SVG, PNG e PDF usando il motore Mermaid del pacchetto fissato e Chromium condiviso, senza un nuovo servizio. Il parser gira con `securityLevel: strict`; non fondare il diagramma su script, callback o icone scaricate in rete.

La sintassi delle versioni più nuove può differire dal renderer della chat: l’export CLI collaudato resta la prova del file consegnato. Mantieni il sorgente testuale e una leggenda leggibile.
