# Capacità operative: xtb

Versione esaminata: **6.5.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Optimize a molecular geometry (XYZ) with the GFN2-xTB semiempirical method; save the optimized structure and native log.
**Sorgenti:** Input geometry, optimized structure and native log.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Optimize a molecular geometry (XYZ) with the GFN2-xTB semiempirical method; save the optimized structure and native log. Semiempirical energies are approximate. | `xtb.optimize` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

GFN2-xTB is approximate; confirm critical energies or geometries with higher-level methods before relying on them.

## Scoperta mirata

1. `craft capabilities xtb`: selezione per obiettivo e confini.
2. `craft commands xtb`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools xtb --out "$RIGHAVEN_OUTPUT_DIR/work/xtb-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `32219834ec176f7a86558cbccd8f76cd97a1769aa00ce07fda41ad63f1e8731c`.
Fonte: https://github.com/grimme-lab/xtb. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
