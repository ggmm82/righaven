# Capacità operative: pari

Versione esaminata: **2.15.2**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Run a PARI/GP script (number theory, exact arithmetic, polynomials) and save its output.
**Sorgenti:** GP script and output.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run a PARI/GP script (number theory, exact arithmetic, polynomials) and save its output. | `pari.evaluate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Some functions are probabilistic (e.g. ispseudoprime); state which results are proven.

## Scoperta mirata

1. `craft capabilities pari`: selezione per obiettivo e confini.
2. `craft commands pari`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools pari --out "$RIGHAVEN_OUTPUT_DIR/work/pari-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `3986725d9bb41a6321ea4004e44d2c19dfcbdc8d8e1dba1d42d730bda9f33447`.
Fonte: https://pari.math.u-bordeaux.fr. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
