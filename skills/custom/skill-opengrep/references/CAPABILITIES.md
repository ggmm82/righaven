# Capacità operative: opengrep

Versione esaminata: **v1.32.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Analisi statica di codice con regole YAML locali esplicite.
**Sorgenti:** Codice o configurazione esaminati, regole locali, report JSON, scan-recipe.json e metadata del database quando usato.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Analisi statica di codice con regole YAML locali esplicite | `opengrep.scan` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Nessuna esecuzione del codice esaminato. I finding richiedono triage; zero finding non significa sicurezza garantita. Non inventare vulnerabilità. Non usare il tool per attacchi. Richiede regole YAML locali; non scarica regole remote automaticamente.

## Scoperta mirata

1. `craft capabilities opengrep`: selezione per obiettivo e confini.
2. `craft commands opengrep`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools opengrep --out "$RIGHAVEN_OUTPUT_DIR/work/opengrep-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `81c1db11b70bb5d1bf49513eaa14c79f7d2363c70b1fe675e9c7cb189b4b313a`.
Fonte: https://github.com/opengrep/opengrep. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
