# Capacità operative: epubcheck

Versione esaminata: **v5.4.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Controllo indipendente EPUB di contenitori, manifest, risorse e markup; errori distinti dagli avvisi.
**Sorgenti:** EPUB e sorgenti XHTML/CSS/OPF, media e font prodotti dagli strumenti di authoring; report JSON come prova.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run independent EPUB conformance validation; report errors and warnings, not editorial or visual quality. | `epubcheck.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Conformità EPUB indipendente, non leggibilità, qualità editoriale, accessibilità completa o compatibilità garantita con ogni lettore. Non ripara automaticamente i problemi.

## Scoperta mirata

1. `craft capabilities epubcheck`: selezione per obiettivo e confini.
2. `craft commands epubcheck`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools epubcheck --out "$RIGHAVEN_OUTPUT_DIR/work/epubcheck-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `fe8a1e2b34793cb89fa6580ab1824d35cec9edb325c77c924a309f58dc207e3a`.
Fonte: https://www.w3.org/publishing/epubcheck/docs/cli/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
