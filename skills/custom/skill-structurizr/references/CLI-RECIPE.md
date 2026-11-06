# Ricetta CLI: Structurizr DSL

1. Scegli la notazione per il problema e conserva la fonte del brief. Compila uno schema corto e leggibile.
2. `structurizr-cli commands` o `craft tools structurizr` descrive i parametri reali. Usa `structurizr-cli call validate '{"input":"/mnt/user-data/model.dsl","output":"/mnt/user-data/outputs/design"}'`. Output sempre nuovo; gli originali sono preservati.
3. Correggi errori e riferimenti mancanti prima di estendere lo schema. Mantieni la semantica nel sorgente, lo stile negli export.
4. Sposta i sorgenti e ripeti il controllo nativo. Il collaudo ripetibile è in `scripts/acceptance_design.py`.
5. In `delivery` separa modello modificabile, SVG/PNG/PDF, ZIP e manuale. Registra le scelte, non ragionamenti privati.

Documentazione ufficiale: https://docs.structurizr.com/dsl.

## C4 da un unico modello

Usa `workspace { model { ... } views { ... } }`, alias stabili per `person`, `softwareSystem`, `container` e `component`, relazioni `a -> b "Descrizione"`. Le viste `systemContext`, `container`, `component`, `dynamic` e `deployment` mostrano livelli diversi dello stesso modello: non creare copie incoerenti.

L’adattatore usa `StructurizrDslParser.setRestricted(true)`, valida il workspace e conserva `workspace.json`; `export` genera PlantUML o Mermaid con gli exporter ufficiali. Il renderer rimane PlantUML/Mermaid, se abilitato. Non installare la vecchia Structurizr CLI o un server per validare/esportare.

Il perimetro è un DSL autonomo senza include, script o plugin. Il C4 riguarda l’architettura software: per libri, edifici o eventi scegli una notazione pertinente al loro contenuto e non chiamare automaticamente ogni componente un software system. Java 21 e dipendenze sono fissati e isolati nel runtime.
