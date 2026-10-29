# Capacità operative: gitleaks

Versione esaminata: **v8.30.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Scan local source directories for leaked credentials without executing the source.
**Sorgenti:** Redacted native findings, scanner identity and remediation guidance; retain original source privately.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Scan a local directory for leaked secrets without executing its code. Native reports are redacted; findings do not imply exploitability. | `gitleaks.scan` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Do not copy discovered secrets into chat or delivery archives. Redact both logs and reports. A match needs triage; remediation may require credential rotation, not only deleting a line.

## Scoperta mirata

1. `craft capabilities gitleaks`: selezione per obiettivo e confini.
2. `craft commands gitleaks`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools gitleaks --out "$RIGHAVEN_OUTPUT_DIR/work/gitleaks-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `c1b50e22c99c5ddcf4dba022660f5d29ee1ec4d367b57e0d47b76fcf026b9715`.
Fonte: https://github.com/gitleaks/gitleaks. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
