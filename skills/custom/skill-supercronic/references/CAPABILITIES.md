# Capacità operative: supercronic

Versione esaminata: **v0.2.50**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Validate a crontab with supercronic and list each job with its schedule; nothing is executed.
**Sorgenti:** Crontab and native validation output.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Validate a crontab with supercronic and list each job with its schedule; nothing is executed. | `supercronic.validate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Validation checks crontab syntax only; job duration, overlaps and time zone must be tested in the target environment.

## Scoperta mirata

1. `craft capabilities supercronic`: selezione per obiettivo e confini.
2. `craft commands supercronic`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools supercronic --out "$RIGHAVEN_OUTPUT_DIR/work/supercronic-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `da96b34d988b21bbce05b4018c6c7adcdc3ab2ab3f7641bfa63275d6b771476a`.
Fonte: https://github.com/aptible/supercronic. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
