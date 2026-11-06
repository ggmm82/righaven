# Capacità operative: ifcopenshell

Versione esaminata: **0.9.0.post1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Authoring semantico BIM e validazione IFC; FreeCAD resta il modellatore CAD parametrico..
**Sorgenti:** IFC, script Python, unità, proprietà e risorse originali..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run an explicit IFC authoring script with the native IfcOpenShell API; preserve script and IFC. | `ifcopenshell.execute` |
| Read native IFC entities, schema, projects and units; not engineering certification. | `ifcopenshell.inspect` |
| Validate the IFC schema with the native validator, reporting actual issues. | `ifcopenshell.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

La validazione dello schema non certifica geometria, normativa o sicurezza strutturale. Non richiede Blender e non ricostruisce uno storico CAD da una mesh.

## Scoperta mirata

1. `craft capabilities ifcopenshell`: selezione per obiettivo e confini.
2. `craft commands ifcopenshell`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools ifcopenshell --out "$RIGHAVEN_OUTPUT_DIR/work/ifcopenshell-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 3 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `30872edd0dc042a38a156174beab80bfa0e0f5d5fe6e90c61a99940dcb1f577f`.
Fonte: https://docs.ifcopenshell.org/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
