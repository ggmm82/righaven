# Capacità operative: usql

Versione esaminata: **v0.21.6**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Use one SQL client across supported relational database drivers for explicit read-only queries..
**Sorgenti:** SQL, bounded result JSON and local database snapshot or external-source requirements..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run a validated SELECT with the native universal SQL client. Use a read-only connection; retain SQL and result JSON, never connection secrets. | `usql.query` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Validate one SELECT, confirm the real driver and use read-only database credentials. Client driver availability does not prove a remote connection was tested.

## Scoperta mirata

1. `craft capabilities usql`: selezione per obiettivo e confini.
2. `craft commands usql`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools usql --out "$RIGHAVEN_OUTPUT_DIR/work/usql-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `f28c1e723d261cc91d251fdf99145767f7e541a059e19cd90bd119b062b5ff9d`.
Fonte: https://github.com/xo/usql. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
