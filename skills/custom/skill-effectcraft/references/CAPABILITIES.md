# Capacità operative: effectcraft

Versione esaminata: **v0.16.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Animazione 2D/3D, motion graphics, compositing, camera/luci ed effetti.
**Sorgenti:** .ecproj e asset; parti, proprietà e keyframe conservati.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Composizioni e livelli | `comp.new`, `comp.settings`, `layer.newPrimitive`, `layer.addShapeItem` |
| Keyframe, curve ed espressioni | `prop.addKey`, `keys.setEase`, `keys.setSpatialTangents`, `prop.setExpression`, `prop.convertExpressionToKeyframes` |
| Camera, luci e 3D | `layer.new3dPrimitive`, `layer.newCamera`, `layer.newLight`, `camera.orbit`, `puppet.mesh` |
| Forme, testi e VFX | `layer.addTextAnimator`, `shape.newPath`, `effect.apply` |
| Audio, render e scambio | `file.import`, `keys.audioToKeyframes`, `renderQueue.add`, `renderQueue.setRenderSettings`, `renderQueue.render` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Advanced 3D può comporre mesh/materiali/camera, oltre alle primitive. Non è un modellatore completo. Modelli complessi possono essere creati in Blender. Render CLI e apertura GUI sono prove distinte. Per asset 3D articolati separa la modellazione dal compositing: importare una mesh e aggiungere primitive non dimostra una modellazione curata. Valuta uno strumento di authoring compatibile con i vincoli e verifica geometria, materiali e parti animabili dopo importazione nel render effettivo.

## Scoperta mirata

1. `craft capabilities effectcraft`: selezione per obiettivo e confini.
2. `craft commands effectcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools effectcraft --out "$RIGHAVEN_OUTPUT_DIR/work/effectcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 731 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `eac7d10ea8d9458d5d56f89ed3cc8a1919ae940b76f190b2ca4215e455bfa765`.
Fonte: https://github.com/storytold/effectcraft/tree/v0.10.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
