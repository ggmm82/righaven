# Capacità operative: netscan

Versione esaminata: **0.7.1**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Inventory and assess networks the owner authorizes: hosts, open ports, services, a network map, and approved non-intrusive vulnerability and TLS checks.
**Sorgenti:** Network connection scope, nmap XML, hosts and services JSON, inventory CSV, Mermaid network map, findings JSON and report.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Find the active hosts of the authorized networks and draw the network map | `netscan.discover` |
| List open ports and identify services and versions | `netscan.services` |
| Check for known vulnerabilities or weak TLS, only with the owner approval of the exact scope | `netscan.vulnerabilities` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Only the networks of a task connection, never outside them. Unprivileged TCP connect probes: no UDP, OS fingerprinting or raw-packet scans. Vulnerability checks are non-intrusive (nmap vuln+safe scripts, testssl.sh) and need the owner approval of each exact scope; no exploitation. Absence of findings is not proof of security.

## Scoperta mirata

1. `craft capabilities netscan`: selezione per obiettivo e confini.
2. `craft commands netscan`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools netscan --out "$RIGHAVEN_OUTPUT_DIR/work/netscan-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 3 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `625eadbbe3f2759813512d0d1e57019a0dbb0f572d3379743afd557f33fb3e14`.
Fonte: https://nmap.org. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
