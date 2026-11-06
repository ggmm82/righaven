# Native recipe: netscan

Discover the exact schema with `netscan-cli commands`. Supported operations: `netscan.discover`, `netscan.services`, `netscan.vulnerabilities`.

1. Use only the Network connection IDs of the task that your role declares.
2. Invoke `netscan-cli call OPERATION 'JSON_ARGUMENTS'` with a fresh absolute `output` directory inside `$RIGHAVEN_OUTPUT_DIR`:
   - `netscan-cli call discover '{"connection":"lan","output":"/…/map-1"}'`
   - `netscan-cli call services '{"connection":"lan","targets":["192.168.1.0/26"],"ports":"common","output":"/…/services-1"}'`
   - `netscan-cli call vulnerabilities '{"connection":"lan","targets":["192.168.1.10"],"profile":"safe","ports":"common","output":"/…/vuln-1"}'` (only as approved)
3. Inspect `receipt.json`, the nmap logs and XML, not only the exit code. "outside the networks" means the target is not authorized; "harness_device_change" means the scan was not approved.
4. Render `network-map.mmd` with Mermaid when a picture helps; keep the inventory as the source.
5. Populate `delivery.files`, `delivery.components`, checks and limitations with the observed evidence.

The executable minimum fixture is `scripts/acceptance_netscan.py`, case `netscan`: mapping with exclusion, service identification, refusal outside the perimeter, refusal without approval and the approved scan.
