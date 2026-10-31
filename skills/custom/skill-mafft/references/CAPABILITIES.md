# Capacità operative: mafft

Versione esaminata: **7.505**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Build a multiple sequence alignment from FASTA with MAFFT --auto; save the aligned FASTA.
**Sorgenti:** Input sequences and aligned FASTA.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Build a multiple sequence alignment from FASTA with MAFFT --auto; save the aligned FASTA. | `mafft.align` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Automatic strategy selection may not suit every family; inspect gaps and conserved regions before phylogenetic use.

## Scoperta mirata

1. `craft capabilities mafft`: selezione per obiettivo e confini.
2. `craft commands mafft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools mafft --out "$RIGHAVEN_OUTPUT_DIR/work/mafft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `27b1645beb6463da53a7c0a56d6d5e5012563d3bbcb6c09d2dc14c104458188d`.
Fonte: https://mafft.cbrc.jp/alignment/software/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
