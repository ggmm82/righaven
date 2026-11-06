# Capacità operative: verapdf

Versione esaminata: **1.30.3**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Validate delivered PDFs against an explicitly chosen PDF/A profile.
**Sorgenti:** Original PDF, selected profile, complete native XML report and receipt.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Validate a PDF against a selected PDF/A profile; save the native XML report and actual conformance status. | `verapdf.validate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Never equate PDF/A conformance with accessibility or visual quality. Do not claim a conversion or certification from a validation report.

## Scoperta mirata

1. `craft capabilities verapdf`: selezione per obiettivo e confini.
2. `craft commands verapdf`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools verapdf --out "$RIGHAVEN_OUTPUT_DIR/work/verapdf-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `d8785c2815c5818386ff27ffe8edf78b70fb18347a20f38acfd17e885f469630`.
Fonte: https://github.com/veraPDF/veraPDF-apps. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
