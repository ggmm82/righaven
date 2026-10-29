# Capacità operative: qpdf

Versione esaminata: **11.3.0-1+deb12u1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Check PDF syntax, cross references and recoverability independently of the authoring tool.
**Sorgenti:** Original PDF, native diagnostics and verification receipt.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Check native PDF syntax and cross references. Warnings remain visible; does not certify PDF/A or visual quality. | `qpdf.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

A warning is not a clean pass. Syntax checks do not certify layout, accessibility, PDF/A or PDF/X; use veraPDF for applicable conformance profiles.

## Scoperta mirata

1. `craft capabilities qpdf`: selezione per obiettivo e confini.
2. `craft commands qpdf`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools qpdf --out "$RIGHAVEN_OUTPUT_DIR/work/qpdf-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `f44a6f9f77adac2a68cb31610b009a3ff1fdf318e70273b09ffb7a90e87f1ba5`.
Fonte: https://github.com/qpdf/qpdf. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
