# Capacità operative: bpmn

Versione esaminata: **0.10.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Processi con eventi, responsabilità, decisioni ed eccezioni in BPMN 2.0; non è un nuovo esecutore dei lavori..
**Sorgenti:** BPMN .bpmn con DI e riferimenti coerenti; SVG/PNG/PDF come export..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| BPMN 2.0 process models with native bpmn-js import and rendering; not a workflow execution engine. Create a portable folder with source, SVG and receipt (browser SDKs also export PNG/PDF). Self-contained inputs only. | `bpmn.render` |
| Validate the self-contained native model and render it; an image alone does not prove design quality. | `bpmn.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief. Il file deve contenere il layout BPMN DI. Le segnalazioni di importazione vanno corrette, non ignorate.

## Scoperta mirata

1. `craft capabilities bpmn`: selezione per obiettivo e confini.
2. `craft commands bpmn`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools bpmn --out "$RIGHAVEN_OUTPUT_DIR/work/bpmn-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `826f227cdaa1d4b1300a86eb2d5b0900cb983d359082a287badee34bf9e28856`.
Fonte: https://bpmn.io/toolkit/bpmn-js. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
