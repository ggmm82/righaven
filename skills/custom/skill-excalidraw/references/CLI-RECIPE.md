# Ricetta CLI: Excalidraw

1. Scegli la notazione per il problema e conserva la fonte del brief. Compila uno schema corto e leggibile.
2. `excalidraw-cli commands` o `craft tools excalidraw` descrive i parametri reali. Usa `excalidraw-cli call render '{"input":"/mnt/user-data/model.excalidraw","output":"/mnt/user-data/outputs/design"}'`. Output sempre nuovo; gli originali sono preservati.
3. Correggi errori e riferimenti mancanti prima di estendere lo schema. Mantieni la semantica nel sorgente, lo stile negli export.
4. Sposta i sorgenti e ripeti il controllo nativo. Il collaudo ripetibile è in `scripts/acceptance_design.py`.
5. In `delivery` separa modello modificabile, SVG/PNG/PDF, ZIP e manuale. Registra le scelte, non ragionamenti privati.

Documentazione ufficiale: https://docs.excalidraw.com.

## Lavagna condivisa e modificabile

Il file nativo è JSON con `type: "excalidraw"`, `version: 2`, `elements`, `appState` e `files`. Ogni elemento conserva ID, tipo, geometria, stile, versione e associazioni; testo e frecce restano oggetti, non una schermata appiattita. Incorpora le immagini come data URL. Mantieni ID e binding delle frecce quando aggiorni una lavagna esistente.

Il wrapper usa `restoreElements`, `exportToSvg` e `serializeAsJSON` dell’SDK ufficiale: `project.excalidraw` è il modello normalizzato, `Sources` conserva l’originale. La console Tavole include l’editor dello stesso SDK, con salvataggio esplicito di una nuova revisione.

Per creare o aggiornare scheletri con l’API nativa consulta `convertToExcalidrawElements`; non riscrivere a caso le proprietà o gli ID di una lavagna approvata. Verifica leggibilità e significato dei collegamenti, poi collega gli ID ad attività/ruoli con `harness_plan(designs_json)`.
