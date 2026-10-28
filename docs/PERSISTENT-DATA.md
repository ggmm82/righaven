# Data across releases

Accounts, chat metadata and message checkpoints share the SQLite database. The managed installation stores it at `/righaven-state/database/righaven_core.db`, on the persistent state volume. User files, native environment definitions and experience live under `/mnt/user-data`; prepared software lives in the internal runtime's data volume. Keep the same Compose project and data volumes when replacing application containers.

The Gateway bootstrap upgrades managed relative SQLite paths to the persistent directory before importing the application. If a database is still available at the previous location, it uses SQLite's backup API, including committed WAL contents, checks integrity and preserves the original. It refuses to overwrite a different existing database. PostgreSQL and explicit custom absolute database paths are unchanged.

## Before upgrading an affected running container

Earlier managed configurations used `.righaven/data`, relative to `/app/backend`. That directory is inside the disposable container. A restart keeps it, but container replacement does not. **Preserve the current database before replacing that container.** Merely installing the corrected image cannot retrieve files from a container that has already been removed.

Use the Hostinger container console or a trusted operator to create a consistent SQLite backup from `/app/backend/.righaven/data/righaven_core.db` into the persistent state volume, without overwriting an existing database. Preserve the old container or its backup until data has been verified. Do not copy only a live SQLite `.db` file while ignoring its WAL. If both old and new databases contain data, keep both; automatic account/database merging is not safe.

If the administrator had to be initialized again, a new user identity was created. Existing environment/source folders may still belong to the previous identity. Restoring chat history requires the former database or a backup; surviving project files alone do not reconstruct all messages or account ownership. Never automatically attach unknown user folders to a newly registered account.

## Release verification

The authenticated Compose test creates an account, a conversation with a message checkpoint, and a prepared native environment. It then **force-recreates the Gateway container**, keeping volumes, and verifies the same account ID, message, environment definition and prepared image ID. A restart alone is not a sufficient persistence test.
