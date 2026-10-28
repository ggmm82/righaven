# Ricetta Blender verificata

Il collaudo in `scripts/acceptance.py`, caso `blender`, crea una mesh realmente 3D con materiale e texture incorporata, animazione a keyframe, camera e luci. Salva `.blend`, lo riapre in un processo distinto, confronta pose a frame diversi, renderizza un PNG CPU, esporta e reimporta un GLB. Sposta e verifica anche il pacchetto sorgenti. È una fixture tecnica, non una direzione artistica.

```bash
craft help blender
craft commands blender
craft tools blender --out "$RIGHAVEN_OUTPUT_DIR/work/blender-tools.json"
blender-cli execute "$RIGHAVEN_OUTPUT_DIR/work/crea_scena.py"
blender-cli inspect "$RIGHAVEN_OUTPUT_DIR/scena.blend"
blender-cli pack "$RIGHAVEN_OUTPUT_DIR/scena.blend" "$RIGHAVEN_OUTPUT_DIR/consegna.blend"
blender-cli render "$RIGHAVEN_OUTPUT_DIR/consegna.blend" "$RIGHAVEN_OUTPUT_DIR/anteprima.png" --frame 1
blender-cli export_glb "$RIGHAVEN_OUTPUT_DIR/consegna.blend" "$RIGHAVEN_OUTPUT_DIR/scena.glb"
```

Lo script usa `bpy.ops.wm.save_as_mainfile(filepath=...)` per salvare; i percorsi devono essere assoluti e nella cartella del lavoro. `pack` crea un file distinto e non sovrascrive gli input. Ogni chiamata MCP è senza stato. In un batch:

```json
[
  {"name":"blender.inspect","arguments":{"project":"/mnt/user-data/outputs/blender/JOB/consegna.blend"}},
  {"name":"blender.render","arguments":{"project":"/mnt/user-data/outputs/blender/JOB/consegna.blend","output":"/mnt/user-data/outputs/blender/JOB/anteprima.png","frame":1}}
]
```

Adatta `JOB` e tutti i percorsi ai file reali. Per render di animazione usa uno script esplicito e checkpoint dei frame. Dopo `delivery`, un revisore distinto confronta i requisiti con il prodotto effettivo: un render valido non certifica contenuto, estetica o movimento.
