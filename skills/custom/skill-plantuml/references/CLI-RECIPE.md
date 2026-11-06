# Ricetta CLI: PlantUML

1. Scegli la notazione per il problema e conserva la fonte del brief. Compila uno schema corto e leggibile.
2. `plantuml-cli commands` o `craft tools plantuml` descrive i parametri reali. Usa `plantuml-cli call render '{"input":"/mnt/user-data/model.puml","output":"/mnt/user-data/outputs/design"}'`. Output sempre nuovo; gli originali sono preservati.
3. Correggi errori e riferimenti mancanti prima di estendere lo schema. Mantieni la semantica nel sorgente, lo stile negli export.
4. Sposta i sorgenti e ripeti il controllo nativo. Il collaudo ripetibile è in `scripts/acceptance_design.py`.
5. In `delivery` separa modello modificabile, SVG/PNG/PDF, ZIP e manuale. Registra le scelte, non ragionamenti privati.

Documentazione ufficiale: https://plantuml.com.

## UML quando serve precisione

Delimita con `@startuml` e `@enduml`. Scegli un solo livello di astrazione: `class` con proprietà/metodi e cardinalità per strutture; `actor`/`participant`, `->` e `-->` per messaggi; `state` per stati; `start`, azioni e `if/endif` per attività. Una sequenza non descrive automaticamente i processi di un evento o il piano di produzione.

Il wrapper usa la CLI Java nativa via stdin, UTF-8, SVG e profilo SECURE. Rifiuta input non validi senza trasformare l’immagine di errore in un prodotto. Gli include sono limitati alla libreria C4 incorporata (`!include <C4/C4_Context>` e analoghi): niente include remoti o letture dell’ambiente.

Gli export C4 di Structurizr usano la libreria standard incorporata. Mantieni sia il modello `.dsl` sia il `.puml` generato e identifica quale è autorevole per le revisioni.
