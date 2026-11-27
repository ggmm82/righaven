# Capacità operative: materialcraft

Versione esaminata: **v0.4.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Creare e riesportare materiali PBR procedurali con un grafo dedicato.
**Sorgenti:** Pacchetto SBS nativo, risorse locali, mappe e anteprima.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Progettazione del grafo | `file.new`, `graph.templates`, `graph.node.add`, `graph.node.param` |
| Materiali portabili | `file.exportMaterial` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Verificare la compatibilità del destinatario. La compatibilità completa con progetti SBS esterni non è dimostrata; TextureCraft 0.6.1 non apre il formato MCMAT v2 esportato da questa versione.

## Scoperta mirata

1. `craft capabilities materialcraft`: selezione per obiettivo e confini.
2. `craft commands materialcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools materialcraft --out "$RIGHAVEN_OUTPUT_DIR/work/materialcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 119 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `54adeb83525216d20fd323428c5dca5178455a0eabf7dc057c7e66f35816301b`.
Fonte: https://github.com/storytold/materialcraft/tree/v0.4.1. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
