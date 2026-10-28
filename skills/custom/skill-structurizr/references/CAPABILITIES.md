# Capacità operative: structurizr

Versione esaminata: **6.2.3**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Viste coerenti di architettura software da un unico modello C4. Usa le librerie mantenute, non la vecchia CLI dismessa..
**Sorgenti:** DSL .dsl, workspace JSON ed export PlantUML/Mermaid; eventuali immagini sono del renderer scelto..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Parse and validate a self-contained C4 DSL using the maintained Structurizr libraries in restricted mode. No server, scripts or plugins. | `structurizr.validate` |
| Export views from one C4 model to editable PlantUML or Mermaid plus workspace JSON; renderer remains the respective existing capability. | `structurizr.export` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Sorgenti autonomi: niente include remoti, script, plugin o risorse esterne non impacchettate. Verifica nativa di sintassi/import e render; non certifica correttezza del progetto. Usa una prova leggibile e controlla relazioni, etichette e coerenza con il brief. Modalità ristretta delle librerie DSL 6.2.3, Java 21 isolato; nessun server o servizio enterprise. Export testuali, non un renderer aggiuntivo.

## Scoperta mirata

1. `craft capabilities structurizr`: selezione per obiettivo e confini.
2. `craft commands structurizr`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools structurizr --out "$RIGHAVEN_OUTPUT_DIR/work/structurizr-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 2 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `1335d22e2dfbf49a286dccb79a429197ccb404ca02fdd63337ab54aae3f8d748`.
Fonte: https://docs.structurizr.com/dsl. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
