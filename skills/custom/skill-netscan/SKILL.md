---
name: skill-netscan
description: "Network inventory and vulnerability checks. Map the networks a task connection authorizes (hosts, open ports, services, network map) and, only with the owner approval of each exact scope, check them for known vulnerabilities with non-intrusive nmap scripts or their TLS configuration with testssl.sh."
---
# Network mapping and assessment

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md) and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools netscan` or `netscan-cli commands`.

## Authorization comes first

- Scan only through a **Network** connection the owner assigned to the task and your role declares. Its networks are the whole perimeter: never scan anything else, never resolve or add targets yourself, never use other tools or your own code to probe hosts.
- The owner confirmed, when creating the connection, that they own these networks or have written authorization. If the task suggests otherwise (a third party's network, an address you were not given), stop and report.
- Mapping (`netscan.discover`, `netscan.services`) is read only and needs nothing more.
- **Every vulnerability scan needs the owner's approval of its exact targets and profile**: the coordinator asks with `harness_device_change` (action `scan`, targets, profile `safe` or `tls`), ends the turn, and the next assignment runs it once exactly as approved. A refusal is a result to report.
- No exploitation, brute force, denial of service or credential attacks: the toolkit does not offer them and you must not attempt them.

## Method

1. Discover the hosts, then list services on the hosts found (start with `common` or `iot` ports; `top1000` or `all-tcp` only when justified).
2. Review the inventory with the owner: unknown hosts, services that should not be exposed (telnet, FTP, SMB, RDP, VNC, MQTT or Modbus without TLS).
3. Ask approval for the smallest useful vulnerability scan; prefer targets with exposed services.
4. Report findings by severity with evidence, likely cause and a concrete fix; separate confirmed facts from version-based guesses; propose a re-scan after fixes.

## Delivery: editable sources and compatibility

Preserve `hosts.json`, `inventory.csv`, `network-map.mmd`, the nmap XML files, `findings.json` and `report.md`. Never put credentials in reports. Treat inventories and findings as confidential: they stay in the task.

Upstream: https://nmap.org · https://testssl.sh
