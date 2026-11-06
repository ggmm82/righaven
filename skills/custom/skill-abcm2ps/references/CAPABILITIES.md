# Capacità operative: abcm2ps

Versione esaminata: **8.14.14**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Engrave ABC music notation into SVG pages, one per tune.
**Sorgenti:** ABC source and SVG score pages.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Engrave ABC music notation into SVG pages, one per tune. | `abcm2ps.engrave` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Engraving shows notation only; listen to the MIDI and review layout before publication.

## Scoperta mirata

1. `craft capabilities abcm2ps`: selezione per obiettivo e confini.
2. `craft commands abcm2ps`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools abcm2ps --out "$RIGHAVEN_OUTPUT_DIR/work/abcm2ps-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `4ddf22f60e4e32eae30873b27de5d2f3a0936e7c5ba35de48f7024aa30a8ef34`.
Fonte: https://github.com/lewdlime/abcm2ps. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
