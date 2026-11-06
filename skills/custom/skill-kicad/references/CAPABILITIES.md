# Capacità operative: kicad

Versione esaminata: **9.0.8+dfsg-1~bpo12+1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Export native electronic schematics and PCBs using headless KiCad CLI.
**Sorgenti:** KICAD_PRO, KICAD_SCH, KICAD_PCB and any custom symbol/footprint libraries, plus fabrication exports when requested.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Export PCB or schematic SVG with native KiCad CLI; preserve native project files and custom libraries. | `kicad.export` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

SVG is an export, not an editable circuit source. Check ERC/DRC and footprints with native tools for manufacturing work; SVG export alone proves neither electrical correctness nor fabrication readiness.

## Scoperta mirata

1. `craft capabilities kicad`: selezione per obiettivo e confini.
2. `craft commands kicad`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools kicad --out "$RIGHAVEN_OUTPUT_DIR/work/kicad-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `cb4816525f4ce75bb5ae5525228daf19422be3af56829ed91d99cdcf400ba9ed`.
Fonte: https://gitlab.com/kicad/code/kicad. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
