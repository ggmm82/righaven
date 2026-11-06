# Capacità operative: beancount

Versione esaminata: **2.3.5**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Check a Beancount ledger: syntax, open accounts, balanced postings and balance assertions.
**Sorgenti:** Ledger file, BQL query and CSV results.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Check a Beancount ledger: syntax, open accounts, balanced postings and balance assertions. Errors are reported, never corrected. | `beancount.check` |
| Run a read-only BQL query on a Beancount ledger and save CSV results. | `beancount.query` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

bean-check validates syntax, accounts and assertions; it does not certify accounting or tax correctness.

## Scoperta mirata

1. `craft capabilities beancount`: selezione per obiettivo e confini.
2. `craft commands beancount`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools beancount --out "$RIGHAVEN_OUTPUT_DIR/work/beancount-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `fa4bc28ef1bba425c1ca6c0a0a589c12be5cad33bc5d0fb00f33d8934abf8fb3`.
Fonte: https://github.com/beancount/beancount. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
