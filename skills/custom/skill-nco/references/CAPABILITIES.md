# Capacità operative: nco

Versione esaminata: **5.1.4**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Print the metadata of a NetCDF file: dimensions, variables, attributes and units.
**Sorgenti:** Original NetCDF, metadata listing and subset file.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Print the metadata of a NetCDF file: dimensions, variables, attributes and units. | `nco.inspect` |
| Extract selected variables of a NetCDF file into a new file. | `nco.subset` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Metadata reflects what the producer wrote; units and conventions still need checking against CF rules.

## Scoperta mirata

1. `craft capabilities nco`: selezione per obiettivo e confini.
2. `craft commands nco`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools nco --out "$RIGHAVEN_OUTPUT_DIR/work/nco-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `5ff29b5c3c65fa5b5d09771142598948e6370459fe4527809a1b1d11bab7c2fd`.
Fonte: https://github.com/nco/nco. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
