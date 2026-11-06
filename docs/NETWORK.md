# Network mapping and security checks

RigHaven can inventory the networks you own and check them for known problems. It is
built for **your own networks** (home, office, lab) or networks you are authorized in
writing to test.

## The pieces

| Piece | Where | Purpose |
|---|---|---|
| **Network connection** | Connections → *New: Network to map* | The perimeter: networks (CIDR or addresses), exclusions, your authorization |
| **netscan toolkit** | Environments → *Network security* | `netscan.discover`, `netscan.services`, `netscan.vulnerabilities` |
| **Network security environment** | Environments, Community Gallery | netscan with ZAP (web), gitleaks, DuckDB and Quarto for analysis and reports |
| **Network security assessment** recipe | Recipes | Scope, inventory and map, approved checks, report with fixes |

## Rules that always apply

- **Only the networks of the connection** are scanned, never anything outside them: the adapter
  and the job both refuse other targets, and excluded addresses are passed to nmap.
- Creating the connection requires confirming that you own the networks or have written
  authorization. Only private networks are accepted unless the administrator sets
  `RIGHAVEN_SCAN_PUBLIC_TARGETS=allow`; private networks need
  `RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS=allow` on a server (the Windows portable app allows them).
  At most 65 536 addresses per connection.
- **Mapping is read only** and needs nothing more: active hosts, open ports, services, the network map.
- **Every vulnerability scan needs your approval of its exact targets and profile.** The
  coordinator asks with `harness_device_change` (action `scan`); you approve or reject under
  *Device and network operations to approve* in the task card; the approval runs once.
- **No attacks.** There is no exploitation, brute force or denial-of-service profile. Checks are
  non-intrusive: nmap scripts that are both `vuln` and `safe`, and testssl.sh for TLS.
- Workers have no raw-socket capability: nmap runs **unprivileged** (TCP connect probes, about
  200 packets per second, 5 minutes per host). UDP services and OS fingerprinting are not observed.
- Every delivery of a network to a task and every decision is written in the audit log.

## Operations

| Operation | Approval | Output |
|---|---|---|
| `netscan.discover` | No | `hosts.json`, `inventory.csv`, `network-map.mmd` (Mermaid), nmap XML |
| `netscan.services` (ports `common`, `iot`, `top100`, `top1000`, `all-tcp`) | No | `services.json`, inventory, map, a list of services to review first (telnet, FTP, SMB, RDP, VNC, MQTT, Modbus, HTTP) |
| `netscan.vulnerabilities` profile `safe` | Yes | `findings.json`, `report.md` with severity (CVSS when reported), CVE identifiers and evidence |
| `netscan.vulnerabilities` profile `tls` | Yes | TLS findings from testssl.sh for up to 20 TLS endpoints |

Software: nmap and testssl.sh from Debian, defusedxml for safe parsing of nmap XML. The
acceptance fixture (`scripts/acceptance_netscan.py`) checks:

- mapping with an exclusion;
- service identification;
- refusal of a target outside the perimeter;
- refusal of a scan without approval;
- the approved scan producing its report.

## Limits

Automated checks find **known** issues only; no findings is not proof of security. A CVE
matched from a version banner is a lead to confirm. Behind NAT (for example WSL 2 on Windows)
MAC addresses and vendors are not visible. With `RIGHAVEN_WORKER_EGRESS=allowlist` scans cannot
reach the network: use the default open egress for these tasks.
