# Capacità operative: samtools

Versione esaminata: **1.16.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Count mapped, paired and duplicate reads of a SAM/BAM/CRAM alignment as TSV.
**Sorgenti:** Original alignment, sorted BAM with index and flag statistics.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Count mapped, paired and duplicate reads of a SAM/BAM/CRAM alignment as TSV. | `samtools.flagstat` |
| Sort an alignment by coordinate into BAM and build its index. | `samtools.sort` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Counts depend on the aligner and flags; they are not a variant call or a clinical result.

## Scoperta mirata

1. `craft capabilities samtools`: selezione per obiettivo e confini.
2. `craft commands samtools`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools samtools --out "$RIGHAVEN_OUTPUT_DIR/work/samtools-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `4e1d5e66027b6ab3058cbd3081a8381b06677cc6e52ac51217f13b9eb2ceb806`.
Fonte: https://github.com/samtools/samtools. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
