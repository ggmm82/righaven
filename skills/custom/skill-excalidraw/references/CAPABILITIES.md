# Capacità operative: excalidraw

Versione esaminata: **0.18.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Brainstorming, mappe e schizzi condivisi; la lavagna resta modificabile dall’utente. VectorCraft resta l’editor vettoriale di produzione..
**Sorgenti:** JSON .excalidraw con immagini incorporate; SVG/PNG/PDF come export..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Editable visual whiteboards, using the native Excalidraw SDK. Create a portable folder with source, SVG and receipt (browser SDKs also export PNG/PDF). Self-contained inputs only. | `excalidraw.render` |
| Validate the self-contained native model and render it; an image alone does not prove design quality. | `excalidraw.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief.

## Scoperta mirata

1. `craft capabilities excalidraw`: selezione per obiettivo e confini.
2. `craft commands excalidraw`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools excalidraw --out "$RIGHAVEN_OUTPUT_DIR/work/excalidraw-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `495e208292a42fd3a7dc918c5470b416f29311f69a68f605262f162c5f3eb7ef`.
Fonte: https://docs.excalidraw.com. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
