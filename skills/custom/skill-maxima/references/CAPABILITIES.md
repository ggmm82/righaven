# Capacità operative: maxima

Versione esaminata: **5.46.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Run a Maxima batch file (symbolic algebra, calculus, equations) and save the transcript.
**Sorgenti:** Batch file and transcript.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run a Maxima batch file (symbolic algebra, calculus, equations) and save the transcript. Check results against the problem statement. | `maxima.evaluate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Symbolic results depend on assumptions (domains, signs); check special cases and conditions stated in the transcript.

## Scoperta mirata

1. `craft capabilities maxima`: selezione per obiettivo e confini.
2. `craft commands maxima`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools maxima --out "$RIGHAVEN_OUTPUT_DIR/work/maxima-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `a0ff7e117a57523919d3aa89970d9a13a3cc14ae3e81a102fbea65fcb9c5eaa3`.
Fonte: https://maxima.sourceforge.io. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
