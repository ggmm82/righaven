# Capacità operative: gdal

Versione esaminata: **3.6.2+dfsg-1+b2**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Inspect raster georeferencing and convert raster datasets to GeoTIFF.
**Sorgenti:** Original geospatial datasets, sidecars, CRS, units, transformation recipe and GeoTIFF.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Read native raster metadata, coordinate reference system, bands and extents into JSON. | `gdal.inspect` |
| Convert a raster to GeoTIFF while preserving the original and recording the recipe. | `gdal.translate` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Confirm CRS, axis order, units, nodata and extents. Format conversion is not reprojection. Do not invent coordinates; advanced vector workflows use the native ogr tools.

## Scoperta mirata

1. `craft capabilities gdal`: selezione per obiettivo e confini.
2. `craft commands gdal`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools gdal --out "$RIGHAVEN_OUTPUT_DIR/work/gdal-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `bd2c2bb2c504e5b3fafa63be522d1a804e15a54ba5c6aadbc3e373726565b77a`.
Fonte: https://github.com/OSGeo/gdal. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
