# Capacità operative: z3

Versione esaminata: **4.8.12**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Check an SMT-LIB 2 problem with the Z3 solver; report sat, unsat or unknown with the model or core it prints.
**Sorgenti:** SMT-LIB problem, solver answer and model.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Check an SMT-LIB 2 problem with the Z3 solver; report sat, unsat or unknown with the model or core it prints. unknown is not a proof. | `z3.solve` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

unknown or a timeout is not a proof; a model satisfies the encoded constraints only, not unstated requirements.

## Scoperta mirata

1. `craft capabilities z3`: selezione per obiettivo e confini.
2. `craft commands z3`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools z3 --out "$RIGHAVEN_OUTPUT_DIR/work/z3-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `0e86f900625978b9d5d4a0328b112afa2e81596e77c24e856a22d2b473786608`.
Fonte: https://github.com/Z3Prover/z3. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
