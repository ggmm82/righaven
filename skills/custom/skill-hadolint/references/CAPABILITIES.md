# Capacità operative: hadolint

Versione esaminata: **v2.14.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Lint a Dockerfile against best practices (including ShellCheck on RUN steps); save JSON findings.
**Sorgenti:** Dockerfile and JSON findings.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Lint a Dockerfile against best practices (including ShellCheck on RUN steps); save JSON findings. | `hadolint.lint` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Best-practice findings do not prove the image builds or is secure; build and scan it separately.

## Scoperta mirata

1. `craft capabilities hadolint`: selezione per obiettivo e confini.
2. `craft commands hadolint`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools hadolint --out "$RIGHAVEN_OUTPUT_DIR/work/hadolint-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `494b139c24d2f187dd0d7bb8538fe582eccdae492c34cfac75bce824f80d3aee`.
Fonte: https://github.com/hadolint/hadolint. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
