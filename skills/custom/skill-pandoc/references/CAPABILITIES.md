# Capacità operative: pandoc

Versione esaminata: **3.12.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Conversione Markdown, DOCX, EPUB, HTML e altri formati, con bibliografia e template espliciti.
**Sorgenti:** Documento strutturato originale, Markdown/AST quando usato, template, bibliografia CSL/BibTeX, font/media e ricetta di conversione.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Convert a structured source into a new document. Preserve templates, bibliography, assets and conversion recipe. | `pandoc.convert` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Conversione semantica, non ricostruzione perfetta di layout complessi o conversione PDF in authoring equivalente. Il PDF richiede un motore di impaginazione esplicito: usa Typst o un percorso collaudato, non LaTeX non installato.

## Scoperta mirata

1. `craft capabilities pandoc`: selezione per obiettivo e confini.
2. `craft commands pandoc`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools pandoc --out "$RIGHAVEN_OUTPUT_DIR/work/pandoc-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `67c7be201f45f38254879da6507c27e126de615b31fddfac06f1ee7096c08aa7`.
Fonte: https://pandoc.org/MANUAL.html. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
