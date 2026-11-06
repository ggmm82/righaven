# Capacità operative: exiftool

Versione esaminata: **12.57**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Read embedded metadata (EXIF, IPTC, XMP, GPS, document properties) of a file into grouped JSON, without changing it.
**Sorgenti:** Original file untouched and grouped metadata JSON.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Read embedded metadata (EXIF, IPTC, XMP, GPS, document properties) of a file into grouped JSON, without changing it. | `exiftool.read` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Listing metadata does not remove it; personal data may also be visible in the content itself.

## Scoperta mirata

1. `craft capabilities exiftool`: selezione per obiettivo e confini.
2. `craft commands exiftool`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools exiftool --out "$RIGHAVEN_OUTPUT_DIR/work/exiftool-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `ee8d741cd03f704418c8db405e2cacda3e648957c3c8b937cc8d28bd497fabf1`.
Fonte: https://exiftool.org. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
