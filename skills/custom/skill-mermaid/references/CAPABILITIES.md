# Capacità operative: mermaid

Versione esaminata: **12.0.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Flussi, sequenze, stati e mappe nella chat e nel Markdown; valorizza il renderer Mermaid già presente in RigHaven..
**Sorgenti:** Mermaid .mmd e ricetta, con SVG/PNG/PDF esportati..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Diagrams for Markdown and chat; export with the existing shared browser engine. Create a portable folder with source, SVG and receipt (browser SDKs also export PNG/PDF). Self-contained inputs only. | `mermaid.render` |
| Validate the self-contained native model and render it; an image alone does not prove design quality. | `mermaid.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief.

## Scoperta mirata

1. `craft capabilities mermaid`: selezione per obiettivo e confini.
2. `craft commands mermaid`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools mermaid --out "$RIGHAVEN_OUTPUT_DIR/work/mermaid-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `a6e1c3ef47019b0b53f9aa1e145f1c7356d8ee899a1b28f6e779a7b1ff9f09ce`.
Fonte: https://mermaid.js.org. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
