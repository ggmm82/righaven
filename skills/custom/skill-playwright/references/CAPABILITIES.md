# Capacità operative: playwright

Versione esaminata: **1.64.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Automazione browser, test di interazione, screenshot e trace su applicazioni web reali.
**Sorgenti:** Codice applicativo, test .test.cjs o automazione .cjs, configurazione, screenshot e trace pertinenti.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Run an explicit local *.test.cjs with Chromium, one worker, JSON report and failure traces. | `playwright.test` |
| Run an explicit local Node .cjs browser automation script; keep script, assertions and evidence. | `playwright.execute` |
| Capture a web URL or a workspace file URL in headless Chromium. Not a visual approval. | `playwright.screenshot` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Collaudo reale Chromium headless CPU; non certifica tutti i browser, accessibilità o qualità visiva. Non vede automaticamente servizi interni: verifica URL e autenticazione. Gli script sono codice eseguito dentro la sandbox, non nel Gateway.

## Scoperta mirata

1. `craft capabilities playwright`: selezione per obiettivo e confini.
2. `craft commands playwright`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools playwright --out "$RIGHAVEN_OUTPUT_DIR/work/playwright-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 3 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `892afd5ea439b449e1817bc660f49e52a3e13915c12ee10b5dec5a46c412e669`.
Fonte: https://playwright.dev/docs/test-cli. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
