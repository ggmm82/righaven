# Capacità operative: minimap2

Versione esaminata: **2.24**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Align reads or assemblies to a reference FASTA into SAM with an explicit preset; alignment is evidence for interpretation, not a variant call.
**Sorgenti:** Reads, reference and SAM alignment.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Align reads or assemblies to a reference FASTA into SAM with an explicit preset; alignment is evidence for interpretation, not a variant call. | `minimap2.align` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Mapping positions depend on preset and reference; alignment is evidence for interpretation, not a variant call.

## Scoperta mirata

1. `craft capabilities minimap2`: selezione per obiettivo e confini.
2. `craft commands minimap2`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools minimap2 --out "$RIGHAVEN_OUTPUT_DIR/work/minimap2-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `f600f0e650fd2e173480e95ed0f83fd1b8cae259469dc7fa79cf8e6aa223765b`.
Fonte: https://github.com/lh3/minimap2. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
