# Ricetta CLI: BPMN / bpmn.io

1. Scegli la notazione per il problema e conserva la fonte del brief. Compila uno schema corto e leggibile.
2. `bpmn-cli commands` o `craft tools bpmn` descrive i parametri reali. Usa `bpmn-cli call render '{"input":"/mnt/user-data/model.bpmn","output":"/mnt/user-data/outputs/design"}'`. Output sempre nuovo; gli originali sono preservati.
3. Correggi errori e riferimenti mancanti prima di estendere lo schema. Mantieni la semantica nel sorgente, lo stile negli export.
4. Sposta i sorgenti e ripeti il controllo nativo. Il collaudo ripetibile è in `scripts/acceptance_design.py`.
5. In `delivery` separa modello modificabile, SVG/PNG/PDF, ZIP e manuale. Registra le scelte, non ragionamenti privati.

Documentazione ufficiale: https://bpmn.io/toolkit/bpmn-js.

## Semantica del processo

Conserva il BPMN 2.0 XML: `definitions`, `process`, eventi iniziali/finali, task, gateway e `sequenceFlow` con `sourceRef`/`targetRef` reali. Usa pool/lane e message flow per responsabilità e scambi fra partecipanti; non usare sequence flow fra pool. Esplicita condizioni e percorsi di eccezione.

Il layout richiede BPMN DI: `BPMNDiagram`, `BPMNPlane`, shape con Bounds ed edge con waypoint. Il parser bpmn-js importa il modello e il renderer produce SVG/PNG/PDF; le segnalazioni di import vengono rifiutate, non nascoste. La console usa il modeler nativo per modificare il disegno e salva il XML con `saveXML`.

Questo modella un processo, non avvia Camunda o un nuovo motore dei lavori. Le attività operative del progetto restano quelle di RigHaven; collega gli ID BPMN alle attività pertinenti invece di mantenere due piani indipendenti.
