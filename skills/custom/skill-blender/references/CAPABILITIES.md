# Capacità operative: blender

Versione esaminata: **5.2.3**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Modellazione 3D, rig, materiali, simulazioni, animazione e rendering.
**Sorgenti:** .blend con risorse incorporate; GLB/FBX/video come export.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Authoring mediante bpy | `blender.execute` |
| Scena, dipendenze e sorgenti | `blender.inspect`, `blender.pack` |
| Rendering e misura dei costi | `blender.profile`, `blender.render` |
| Scambio glTF | `blender.export_glb` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

L’adattatore espone poche operazioni sicure; execute permette authoring con bpy, non soltanto quelle del menu Craft. Le operazioni dipendono dalla versione Blender, da add-on e risorse. Ogni chiamata apre un processo: salvare il .blend.

## Scoperta mirata

1. `craft capabilities blender`: selezione per obiettivo e confini.
2. `craft commands blender`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools blender --out "$RIGHAVEN_OUTPUT_DIR/work/blender-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 6 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `9adaff19e8a1d480f9fe34b2b54166f1f015ea57c8da617a77753cde7db3c45d`.
Fonte: https://projects.blender.org/blender/blender. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
