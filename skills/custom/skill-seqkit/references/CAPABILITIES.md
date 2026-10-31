# Capacità operative: seqkit

Versione esaminata: **2.3.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Summarize FASTA/FASTQ files: counts, lengths, N50, GC and quality fractions as TSV.
**Sorgenti:** Original sequences, filtered files and statistics.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Summarize FASTA/FASTQ files: counts, lengths, N50, GC and quality fractions as TSV. | `seqkit.stats` |
| Keep sequences within a length range, optionally reverse-complemented, into a new FASTA/FASTQ. | `seqkit.filter` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Statistics describe the files; they do not assess biological quality, contamination or sample identity.

## Scoperta mirata

1. `craft capabilities seqkit`: selezione per obiettivo e confini.
2. `craft commands seqkit`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools seqkit --out "$RIGHAVEN_OUTPUT_DIR/work/seqkit-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `248f85ed6b2bc24fe395f7ff9c308292de479e0fdfa7055d38f19a7859249074`.
Fonte: https://github.com/shenwei356/seqkit. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
