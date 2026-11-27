# Capacità operative: ruff

Versione esaminata: **0.17.6**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Controlla e formatta sorgenti Python e notebook.
**Sorgenti:** File .py/.ipynb originali o revisionati, configurazione di lint e report.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Qualità del codice Python | `check`, `format`, `rule` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Il lint non verifica esecuzione, risultati dei notebook o regole di business. Applicare correzioni solo alle copie di lavoro e verificare le differenze.

## Scoperta mirata

1. `craft capabilities ruff`: selezione per obiettivo e confini.
2. `craft commands ruff`: registro integrale; cerca soltanto gli ID pertinenti.
3. Usa `craft run ruff -- <comando>` per eseguire la CLI.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 10 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `d56cf474c6f6141ba1af426cab55f1c376475838deb9c5241f1fd558cc189569`.
Fonte: https://github.com/astral-sh/ruff. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
