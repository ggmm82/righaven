# Capacità operative: lightcraft

Versione esaminata: **v0.13.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Sviluppo fotografico/RAW, catalogazione, correzioni locali e serie coerenti.
**Sorgenti:** Originali, parametri e ricetta riproducibile; sidecar solo se realmente supportato.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Sviluppo e ottica | `develop.set`, `develop.adjust`, `develop.reset`, `develop.updateProcess` |
| Curve, colore e ritaglio | `develop.curve`, `pointColor.pick`, `crop.set`, `crop.straighten` |
| Maschere locali | `mask.add`, `mask.addComponent`, `mask.brushStroke`, `mask.update` |
| Catalogo e selezione | `library.source`, `library.filter`, `library.folders`, `library.removeFolder` |
| Denoise e modelli | `denoise.models.list`, `denoise.models.inspect`, `denoise.models.install`, `denoise.models.test`, `denoise.queue`, `denoise.status` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Funzioni AI/denoise dipendono dai modelli effettivamente installati. Una voce del catalogo non prova disponibilità dei pesi o di un servizio remoto.

## Scoperta mirata

1. `craft capabilities lightcraft`: selezione per obiettivo e confini.
2. `craft commands lightcraft`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools lightcraft --out "$RIGHAVEN_OUTPUT_DIR/work/lightcraft-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 371 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `c63fec40fef29cd74877448cbe3a805320817d90988ec59eb030102daedc9195`.
Fonte: https://github.com/storytold/lightcraft/tree/v0.8.0. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
