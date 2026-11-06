# Quality: netscan

- The container has no raw sockets: nmap uses TCP connect probes. Hosts that answer on none of the probed ports, UDP services and OS fingerprints are not observed; say so.
- Versions come from banners and can be wrong or hidden; a CVE matched only by version is a lead, not a confirmed vulnerability.
- `safe` runs only nmap scripts in both the `vuln` and `safe` categories; it does not prove the absence of other issues.
- Rate is limited (200 packets per second, 5 minutes per host); large networks take time: split them.
- Every finding names host, port, check, severity, evidence and a fix; repeat the scan after the fix and compare.
