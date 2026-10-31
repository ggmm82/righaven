# Capacità operative: openbabel

Versione esaminata: **3.1.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Convert molecules between SMILES, SDF, MOL, MOL2, XYZ, PDB, CML and InChI; optionally generate 3D coordinates.
**Sorgenti:** Original molecule file, converted structure and descriptor table.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Convert molecules between SMILES, SDF, MOL, MOL2, XYZ, PDB, CML and InChI; optionally generate 3D coordinates. Generated geometry is a starting point, not a validated conformer. | `openbabel.convert` |
| Compute formula, molecular weight, logP and TPSA per molecule. Descriptors are estimates, not measurements. | `openbabel.properties` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Generated 3D coordinates and descriptors (logP, TPSA) are estimates; they are not validated conformers or measurements.

## Scoperta mirata

1. `craft capabilities openbabel`: selezione per obiettivo e confini.
2. `craft commands openbabel`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools openbabel --out "$RIGHAVEN_OUTPUT_DIR/work/openbabel-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `9af7e54878a0b125742c5f8dbdb655c06d664d1377dcbda18f5618ede16b363a`.
Fonte: https://github.com/openbabel/openbabel. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
