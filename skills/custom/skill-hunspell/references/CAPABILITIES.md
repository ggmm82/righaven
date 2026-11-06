# Capacità operative: hunspell

Versione esaminata: **1.7.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** List words not found in the Italian or English Hunspell dictionary; names and technical terms need human review.
**Sorgenti:** Text and list of unknown words.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| List words not found in the Italian or English Hunspell dictionary; names and technical terms need human review. | `hunspell.check` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Unknown words include names and technical terms; grammar, style and meaning are not checked.

## Scoperta mirata

1. `craft capabilities hunspell`: selezione per obiettivo e confini.
2. `craft commands hunspell`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools hunspell --out "$RIGHAVEN_OUTPUT_DIR/work/hunspell-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `b23b6d6013b7827a0348438b87e191d271202e7d1fcbadb109a10e1166fb23a1`.
Fonte: https://github.com/hunspell/hunspell. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
