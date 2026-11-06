# Capacità operative: mat2

Versione esaminata: **0.13.3**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** List the metadata mat2 would remove from a document, image or media file.
**Sorgenti:** Original file preserved, cleaned copy and removed metadata list.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| List the metadata mat2 would remove from a document, image or media file. | `mat2.inspect` |
| Write a cleaned copy without metadata; the original is preserved. Visible content (faces, text, watermarks) is not anonymized. | `mat2.clean` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Removes embedded metadata only; faces, text, watermarks or hidden layers in the visible content are not anonymized.

## Scoperta mirata

1. `craft capabilities mat2`: selezione per obiettivo e confini.
2. `craft commands mat2`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools mat2 --out "$RIGHAVEN_OUTPUT_DIR/work/mat2-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `8917b11467c8bab6489a96ffe01001c4d85c4f7b536adc7a1ab086fb9e7c53b8`.
Fonte: https://0xacab.org/jvoisin/mat2. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
