# Capacità operative: fontforge

Versione esaminata: **20230101**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Open a font (TTF, OTF, SFD, UFO, WOFF) and generate it in another format, reporting the glyph count.
**Sorgenti:** Original font, generated font and glyph count.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Open a font (TTF, OTF, SFD, UFO, WOFF) and generate it in another format, reporting the glyph count. Font licences still apply. | `fontforge.convert` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Format conversion keeps outlines but may drop hinting or features; font licences still apply.

## Scoperta mirata

1. `craft capabilities fontforge`: selezione per obiettivo e confini.
2. `craft commands fontforge`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools fontforge --out "$RIGHAVEN_OUTPUT_DIR/work/fontforge-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `f249629b93498d28ab0b7bfaa78af5101751f18205cacee7d1b75f8335266b57`.
Fonte: https://github.com/fontforge/fontforge. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
