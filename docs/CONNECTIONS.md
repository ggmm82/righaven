# Connections

**Connections** (sidebar → *Configuration*) holds each user's own database and Microsoft cloud
accounts. Tasks use them only when the user assigns them, and each assignment receives only the
connections its role declares.

| Kind | Fields | Usable with |
|---|---|---|
| PostgreSQL | server, port (5432), database, user, password, TLS (`sslmode=require`) | usql, dlt, SchemaCrawler |
| SQL Server / Azure SQL / Fabric (SQL user) | server, port (1433), database, user, password, encryption | usql, dlt (pymssql), SchemaCrawler |
| SQL Server / Azure SQL / Fabric (Entra ID) | server, database, a Microsoft Entra ID connection | usql (`azuresql`, `fedauth=ActiveDirectoryServicePrincipal`) |
| MySQL / MariaDB | server, port (3306), database, user, password, TLS | usql, dlt, SchemaCrawler |
| Microsoft Entra ID | tenant (ID or domain), application (client) ID, client secret, cloud (global, US Government, China) | the SQL connections above; Fabric and Power BI APIs |

## How it works

1. **Create** the connection. Passwords and client secrets are encrypted with the installation's
   credentials key (`RIGHAVEN_CREDENTIALS_KEY`, or the key generated at first start), are never shown
   again and never reach the coordinator. Leaving a secret empty when editing keeps the stored one.
2. **Test** it. For databases the test checks that RigHaven reaches `server:port`; user and password are
   proven at first use in an assignment. For Entra ID it requests a real token
   (`client_credentials`, scope `https://database.windows.net/.default`) and reports Microsoft's
   error code when refused.
3. **Declare read-only.** RigHaven's adapters only read, and they refuse database connections the
   user has not declared read-only. Use an account with read permissions only.
4. **Assign** it to a task from the project panel (*Task connections*). The coordinator then sees the
   connection's name, kind, server, database and the tools that support it, never its secret.
5. **Use.** A role declares `connections: ["ID"]`; when that assignment starts, RigHaven decrypts only
   those connections into a private folder mounted read-only at `/run/righaven/connections/ID.json`,
   and deletes it when the worker ends. The adapters take `connection: "ID"` and redact the values
   from native logs; connection files never enter sources, receipts or lessons.

## Network

- The test runs from the Gateway. Servers resolving to private, loopback or link-local addresses are
  refused unless the operator sets `RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS=allow` (for on-premises
  databases reachable from the RigHaven host).
- With the default worker network, assignments connect directly. With
  `RIGHAVEN_WORKER_EGRESS=allowlist` assignments can only use HTTPS through the proxy: Entra ID,
  Fabric and Power BI domains are granted automatically for assignments with an Entra connection, but
  database protocols (TDS, PostgreSQL, MySQL) are not proxied and the databases are not reachable.

## Not verified by RigHaven

The Entra ID service principal path for SQL connections relies on the go-mssqldb `azuresql` driver
built into usql; it has not been exercised against a real Azure SQL or Fabric endpoint by the
repository tests. Grant the application access to the database (for Fabric: workspace or item
permissions) before use.
