# Capacità operative: freecad

Versione esaminata: **1.1.4**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Modellazione CAD 3D parametrica di oggetti, componenti e costruzioni; sorgenti modificabili e scambio STEP.
**Sorgenti:** Documento nativo .FCStd con albero parametrico, script .py realmente usato, dati e riferimenti; STEP come export di scambio.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run an explicit Python authoring script in native headless FreeCAD; save .FCStd and geometry evidence in the output folder. | `freecad.execute` |
| Reopen .FCStd, report native objects, parametric properties and solid volumes. No GUI or engineering certification. | `freecad.inspect` |
| Reopen .FCStd and export selected solid shapes to a new STEP; STEP is not a parametric authoring source. | `freecad.export_step` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Motore headless FreeCAD 1.1.4 dalla distribuzione ufficiale, eseguito con il Python incluso. Verifica le API della versione fissata. STEP conserva geometria di scambio, non lo storico parametrico .FCStd; nessuna certificazione ingegneristica o prova GUI implicita. Può costruire asset rigidi destinati ad altre app: il passaggio al renderer richiede un formato importabile, tassellazione, orientamento, unità e materiali verificati. L’adattatore espone STEP e script execute, non un’esportazione OBJ/GLB già certificata. Eventuali esportazioni mesh tramite API native vanno provate; STEP non è automaticamente importabile in un compositore. Non è un sostituto universale di rig, modellazione organica o animazione.

## Scoperta mirata

1. `craft capabilities freecad`: selezione per obiettivo e confini.
2. `craft commands freecad`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools freecad --out "$RIGHAVEN_OUTPUT_DIR/work/freecad-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 3 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `36a22868e1df180eee35a31b4f7a316030bc3cebe17bd9c5eb59565fa801157b`.
Fonte: https://freecad.github.io/SourceDoc/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
