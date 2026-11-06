# Capacità operative: plantuml

Versione esaminata: **v1.2026.9**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Classi, sequenze, attività e stati quando la semantica UML è utile; D2 resta la scelta per schemi generali..
**Sorgenti:** PlantUML .puml autonomo e ricetta; SVG come export..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Formal UML from editable PlantUML, with native syntax checking. Create a portable folder with source, SVG and receipt (browser SDKs also export PNG/PDF). Self-contained inputs only. | `plantuml.render` |
| Validate the self-contained native model and render it; an image alone does not prove design quality. | `plantuml.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief.

## Scoperta mirata

1. `craft capabilities plantuml`: selezione per obiettivo e confini.
2. `craft commands plantuml`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools plantuml --out "$RIGHAVEN_OUTPUT_DIR/work/plantuml-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `4401122f6206f0eb7b01421d7fc8b8a9240e46af8534173726b7b4f8f4ebb70f`.
Fonte: https://plantuml.com. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
