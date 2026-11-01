# Connections

**Connections** (sidebar → *Configuration*) holds each user's own database and Microsoft cloud
accounts. Access is the user's choice: the connections ticked for a task are delivered to every
assignment of that task and to no other.

| Kind | Fields | Usable with |
|---|---|---|
| PostgreSQL | server, port (5432), database, user, password, TLS (`sslmode=require`) | usql, dlt, SchemaCrawler |
| SQL Server / Azure SQL / Fabric (SQL user) | server, port (1433), database, user, password, encryption | usql, dlt (pymssql), SchemaCrawler |
| SQL Server / Azure SQL / Fabric (Entra ID) | server, database, a Microsoft Entra ID connection (your account or an application) | usql (`azuresql`; access token for your account, `fedauth=ActiveDirectoryServicePrincipal` for an application) |
| MySQL / MariaDB | server, port (3306), database, user, password, TLS | usql, dlt, SchemaCrawler |
| Oracle | server, port (1521), service name, user, password | usql (go-ora), dlt (`oracledb` thin mode), SchemaCrawler |
| Microsoft Entra ID · my account (default) | optional tenant (domain or ID, default `organizations`), optional public client ID, cloud; then **Sign in with Microsoft** | the SQL connections above with your own database permissions; Fabric API token when consented |
| Microsoft Entra ID · application | tenant (ID or domain), application (client) ID, client secret, cloud (global, US Government, China) | the SQL connections above; Fabric and Power BI APIs |

## How it works

1. **Create** the connection. Passwords and client secrets are encrypted with the installation's
   credentials key (`RIGHAVEN_CREDENTIALS_KEY`, or the key generated at first start), are never shown
   again and never reach the coordinator. Leaving a secret empty when editing keeps the stored one.
2. **Test** it. For databases the test checks that RigHaven reaches `server:port`; user and password are
   proven at first use in an assignment. For an Entra ID application it requests a real token
   (`client_credentials`, scope `https://database.windows.net/.default`); for your account it
   exchanges the saved sign-in for a token. Microsoft's error code is reported when refused.
3. **Declare read-only.** RigHaven's adapters only read, and they refuse database connections the
   user has not declared read-only. Use an account with read permissions only. For a destination see
   *Writing into a destination* below.
4. **Assign** it to a task from the project panel (*Task connections*). The coordinator then sees the
   connection's name, kind, server, database and the tools that support it, never its secret.
5. **Use.** When an assignment of the task starts, RigHaven decrypts the task's connections into a
   private folder mounted read-only at `/run/righaven/connections/ID.json`, and deletes it when the
   worker ends. The adapters take `connection: "ID"` and redact the values
   from native logs; connection files never enter sources, receipts or lessons.

## Pasting a server URL or connection string

The *Server* field accepts what you copy from a portal: a host name, `host:port`,
`tcp:host,port`, a URL (`postgresql://user@host:5432/db`, `sqlserver://…`), a JDBC string
(`jdbc:sqlserver://host:1433;databaseName=db;user=…`) or an ADO/ODBC string
(`Server=tcp:host,1433;Initial Catalog=db;User ID=…`). Server, port, database and user are read
from it; fields you fill explicitly win. Passwords inside a pasted string are not stored: use the
password field. Named instances (`host\INSTANCE`) need the TCP port instead.

## SQL Server with your Microsoft account

For Azure SQL and Fabric choose **SQL Server / Azure SQL / Fabric** with authentication **My
Microsoft account**: enter or paste the server, your account email and, optionally, the database.
Save, press **Sign in with Microsoft** (device code and multi-factor authentication on Microsoft's
page, as below) and then **List databases**: RigHaven shows the databases your account can see on
that server and **Use this database** selects one. Signing in with a different account than the
email of the connection is refused.

The list comes from Microsoft's management APIs, not from a database login: Azure SQL databases
through Azure Resource Manager (your account needs read access to the server resource), Fabric
warehouses, lakehouse SQL endpoints and SQL databases through the Fabric REST API (workspace
membership). When the account has no such access, or for other servers, type the database name.

## Your Microsoft account as a separate identity (OAuth2 with multi-factor authentication)

A Microsoft Entra ID connection in *My Microsoft account* mode can also be shared by several SQL
connections (authentication *Entra ID application or account already registered*).

For Azure SQL, Fabric SQL endpoints and SQL Server with Entra ID you normally use **your own work or
school account**, not an application registered in the tenant:

1. Create *New: Microsoft Entra ID* and keep **My Microsoft account**. Tenant and client ID are
   optional: the default tenant `organizations` accepts any work or school account, and the default
   public client is the Microsoft Azure CLI application (`04b07795-8ddb-461a-bbee-02f9e1bf7b46`),
   which most tenants already allow for Azure SQL. An organization may register its own public
   client (no secret, *Allow public client flows*, delegated `Azure SQL Database user_impersonation`)
   and enter its ID.
2. Press **Sign in with Microsoft**. RigHaven starts the OAuth2 device authorization flow and shows a
   code and Microsoft's page (`https://microsoft.com/devicelogin`). Enter the code there and complete
   password, multi-factor authentication and any Conditional Access requirement on Microsoft's
   page. RigHaven never sees your password or second factor.
3. RigHaven stores only the **refresh token**, encrypted like the other secrets, and shows the
   signed-in account. *Test* exchanges it for a token; *Disconnect account* deletes it. Changing
   tenant, client or cloud requires a new sign-in.
4. Create a SQL Server connection with authentication *Microsoft Entra ID* that uses this account.
5. When an assignment starts, the Gateway exchanges the refresh token for a **short-lived access
   token** (about one hour) for the database (`https://database.windows.net/.default`, or the
   sovereign cloud equivalent) and, on the global cloud, a Fabric API token
   (`https://api.fabric.microsoft.com/.default`) when consented. Only those tokens reach the
   worker; the refresh token never leaves the Gateway. Rotated refresh tokens are saved. usql
   receives `azuresql://…?fedauth=ActiveDirectoryServicePrincipalAccessToken` with the token as
   password.

Limits: assignments longer than the token lifetime must be split or restarted. If the tenant's
Conditional Access blocks the device code flow (error `AADSTS53003`) or the refresh token is
revoked or expires (`AADSTS700082`, password change, sign-in frequency policy), sign in again, ask
the administrator to allow the flow for RigHaven, or use an application connection. Database
permissions are those of your account: grant yourself read-only access, and declare the SQL
connection read-only.

## Writing into a destination

Sources stay read-only. A destination, such as a staging schema of the warehouse that the BI reads,
can receive data from RigHaven:

1. In the connection choose **Read and write in a dedicated schema** and name the schema (for
   example `righaven`). Use a database account whose permissions are limited to that schema.
2. In the task card, *Task connections*, assign the connection and tick **Allow writing in this
   task**. Without that tick the task receives the connection read-only. Each task decides on its own.
3. The team can then only run `dlt.load`: it copies tables already verified in the local DuckDB
   files (for example the reconciled marts, or `raw.table` after an ingestion run) into that schema,
   replacing or appending them. There is no free SQL, no other schema and at most one million rows per
   load. Each delivery of write access is recorded in the task log; the load receipt lists tables,
   rows, mode and target.

Connections with a SQL user and password write through SQLAlchemy (PostgreSQL, MySQL/MariaDB, SQL
Server, Oracle). Connections with your Microsoft account (Azure SQL, Fabric Warehouse) write T-SQL
through usql with a short-lived token; this path has not been exercised against a real Azure or
Fabric target by the repository tests (CI loads into a SQLite file).

## Network

- The test runs from the Gateway. Servers resolving to private, loopback or link-local addresses are
  refused unless the operator sets `RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS=allow` (for on-premises
  databases reachable from the RigHaven host).
- With the default worker network, assignments connect directly. With
  `RIGHAVEN_WORKER_EGRESS=allowlist` assignments can only use HTTPS through the proxy: Entra ID,
  Fabric and Power BI domains are granted automatically for assignments with an Entra connection, but
  database protocols (TDS, PostgreSQL, MySQL, Oracle Net) are not proxied and the databases are not reachable.

## Not verified by RigHaven

The Entra ID paths for SQL connections (personal access token and service principal) rely on the
go-mssqldb `azuresql` driver built into usql, and Oracle relies on usql's go-ora driver and
python-oracledb thin mode. The repository tests exercise the device code sign-in against a simulated
Microsoft endpoint, not real Azure SQL, Fabric or Oracle servers. Grant your account or the application access to the database (for Fabric: workspace or item
permissions) before use.
