# Capacità operative: cdo

Versione esaminata: **2.1.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Describe a NetCDF/GRIB dataset: variables, grid, levels and time steps.
**Sorgenti:** Original dataset, derived NetCDF and dataset description.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Describe a NetCDF/GRIB dataset: variables, grid, levels and time steps. | `cdo.info` |
| Compute a time or field statistic of a NetCDF/GRIB dataset into a new NetCDF file. | `cdo.statistic` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Statistics follow the grid and calendar of the data; check units, missing values and grid cell areas before conclusions.

## Scoperta mirata

1. `craft capabilities cdo`: selezione per obiettivo e confini.
2. `craft commands cdo`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools cdo --out "$RIGHAVEN_OUTPUT_DIR/work/cdo-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `37d338f8494b40942d307553648300288c48a217ac6384b5c518f26e4ecd53b8`.
Fonte: https://code.mpimet.mpg.de/projects/cdo. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
