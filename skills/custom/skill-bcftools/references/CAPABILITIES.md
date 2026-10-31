# Capacità operative: bcftools

Versione esaminata: **1.16**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Summarize a VCF/BCF: records, SNPs, indels, transitions/transversions and quality distributions.
**Sorgenti:** Original VCF/BCF and native statistics.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Summarize a VCF/BCF: records, SNPs, indels, transitions/transversions and quality distributions. | `bcftools.stats` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Variant statistics are descriptive; interpretation, filtering thresholds and clinical meaning need expert review.

## Scoperta mirata

1. `craft capabilities bcftools`: selezione per obiettivo e confini.
2. `craft commands bcftools`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools bcftools --out "$RIGHAVEN_OUTPUT_DIR/work/bcftools-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `0702ab2771f88728cccc2ff6f8dbbe9749e5312192a0b3a00d18c1599a5bb396`.
Fonte: https://github.com/samtools/bcftools. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
