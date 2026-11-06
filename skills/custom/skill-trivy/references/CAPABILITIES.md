# Capacità operative: trivy

Versione esaminata: **v0.76.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Controllo configurazioni, inventario CycloneDX e vulnerabilità con database esplicito.
**Sorgenti:** Codice o configurazione esaminati, regole locali, report JSON, scan-recipe.json e metadata del database quando usato.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Controllo configurazioni, inventario CycloneDX e vulnerabilità con database esplicito | `trivy.config`, `trivy.sbom`, `trivy.database_update`, `trivy.vulnerabilities` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Nessuna esecuzione del codice esaminato. I finding richiedono triage; zero finding non significa sicurezza garantita. Non inventare vulnerabilità. Non usare il tool per attacchi. Config usa controlli incorporati. SBOM non equivale a vulnerability scan. Vulnerabilities richiede database aggiornato esplicitamente con database_update: l’assenza del DB è un errore, mai zero finding.

## Scoperta mirata

1. `craft capabilities trivy`: selezione per obiettivo e confini.
2. `craft commands trivy`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools trivy --out "$RIGHAVEN_OUTPUT_DIR/work/trivy-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 4 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `4d8f7f0a0e266547fa8dcc19b3e3f5a8cb2455a33251f6e49a77ddec551a969b`.
Fonte: https://github.com/aquasecurity/trivy. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
