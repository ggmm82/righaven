# Capacità operative: mjml

Versione esaminata: **5.4.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Compile an MJML email template into responsive HTML with strict validation.
**Sorgenti:** MJML source and compiled HTML.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Compile an MJML email template into responsive HTML with strict validation. Rendering still differs by email client. | `mjml.compile` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Compiled HTML still renders differently across email clients; test in the target clients before sending.

## Scoperta mirata

1. `craft capabilities mjml`: selezione per obiettivo e confini.
2. `craft commands mjml`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools mjml --out "$RIGHAVEN_OUTPUT_DIR/work/mjml-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `6d8b98557446e81a744b95c440c7f7ed9ab607f43f6a624113cf6d76c1889017`.
Fonte: https://github.com/mjmlio/mjml. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
