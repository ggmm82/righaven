# Acceptance and boundaries: GDAL

- Outcome: verify the requested content and native format, rather than treating an exit code or a file extension as quality.
- Reproducibility: retain Original geospatial datasets, sidecars, CRS, units, transformation recipe and GeoTIFF.
- Native integrity: parse or reopen actual output, test a known expected result, and preserve failed checks. Verify dependencies after relocation when the product links resources.
- Scope: Confirm CRS, axis order, units, nodata and extents. Format conversion is not reprojection. Do not invent coordinates; advanced vector workflows use the native ogr tools.
- Delivery: distinguish primary product, editable source, preview and report; document opening/editing instructions and any prerequisite missing outside RigHaven.
- Independent review: use the modality the criterion requires. If unavailable, mark it `not_run` and provide a concrete next step; do not rewrite the product repeatedly to compensate for missing verification.
