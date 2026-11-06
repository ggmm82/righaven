# Capacità operative: pymeshlab

Versione esaminata: **2025.7.post1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Misura, pulizia e filtri di mesh esistenti; FreeCAD resta il CAD parametrico e Blender l’authoring organico..
**Sorgenti:** MLP, geometrie PLY/OBJ/STL, filtri MLX o Python, risorse collegate..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run an explicit native mesh-processing script. Preserve input geometry and filter/Python recipe; not parametric CAD authoring. | `pymeshlab.execute` |
| Reopen a mesh or MLP project and measure actual geometry. | `pymeshlab.inspect` |
| Apply an explicit native MLX filter script and save geometry, recipe and a portable MLP project. | `pymeshlab.apply` |
| Save the actually registered native filter names; registration is not an execution proof. | `pymeshlab.filters` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Non ricostruisce automaticamente CAD parametrico, rig o texture. L’adattatore apply produce una mesh PLY: per asset texturizzati preservare risorse e usare uno script esplicito con verifica delle UV. Un filtro registrato non è una prova di efficacia.

## Scoperta mirata

1. `craft capabilities pymeshlab`: selezione per obiettivo e confini.
2. `craft commands pymeshlab`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools pymeshlab --out "$RIGHAVEN_OUTPUT_DIR/work/pymeshlab-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 4 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `b44712a3aaf3c80123d4884d082b07bb602a86f41691fe1ce0f04cacba16f69d`.
Fonte: https://pymeshlab.readthedocs.io/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
