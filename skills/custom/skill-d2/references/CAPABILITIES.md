# Capacità operative: d2

Versione esaminata: **v0.9.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Flussi, relazioni e dipendenze con layout automatico; non richiede UML o professioni fisse..
**Sorgenti:** D2 .d2 autonomo e ricetta; SVG/PNG/PDF come export..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Modern structured diagrams with automatic layout from editable D2. Create a portable folder with source, SVG and receipt (browser SDKs also export PNG/PDF). Self-contained inputs only. | `d2.render` |
| Validate the self-contained native model and render it; an image alone does not prove design quality. | `d2.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief.

## Scoperta mirata

1. `craft capabilities d2`: selezione per obiettivo e confini.
2. `craft commands d2`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools d2 --out "$RIGHAVEN_OUTPUT_DIR/work/d2-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `4aab65274c46e7271d00543f9cfcfe22d4f9ae203c3d0d5737a00aba0be75474`.
Fonte: https://d2lang.com. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
