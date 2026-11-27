# Capacità operative: frictionless

Versione esaminata: **5.21.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Genera descrittori Data Package e valida CSV e schemi forniti.
**Sorgenti:** Dataset, datapackage.json con riferimenti relativi e report JSON.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Contratti per dati tabellari | `describe`, `validate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Uno schema inferito è una bozza: tipi, chiavi e vincoli richiedono conferma. Validare descrittori locali controllando i percorsi delle risorse.

## Scoperta mirata

1. `craft capabilities frictionless`: selezione per obiettivo e confini.
2. `craft commands frictionless`: registro integrale; cerca soltanto gli ID pertinenti.
3. Usa `craft run frictionless -- <comando>` per eseguire la CLI.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 10 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `f80c02b63d52b68af4c1b597b194027901c82e3824f78750aad7679cae4b3634`.
Fonte: https://github.com/frictionlessdata/framework. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
