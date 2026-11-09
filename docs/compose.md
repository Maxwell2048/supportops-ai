# Local application stack and recovery

`compose.full.yaml` defines a separate local project named `supportops-app`, with PostgreSQL, a one-shot migration, API, mock worker and static frontend. Its database volume is distinct from the database-only Compose stack. It publishes the web service on loopback port 8080 by default. Docker Desktop and a root `.env` with a PostgreSQL password and JWT secret are required. The existing `.env` is excluded from image build contexts. This stack is intended for local synthetic-data use.

From the repository root in PowerShell:

```powershell
docker compose -f compose.full.yaml up --build -d --wait
# Set a local password in the environment, without putting it in command history.
# Then explicitly activate the synthetic accounts:
docker compose -f compose.full.yaml exec -T -e DEMO_PASSWORD api python -m supportops.compose_demo
```

Open `http://127.0.0.1:8080`. The seed command inserts missing synthetic fixtures and activates only accounts still marked as never activated. It preserves existing account passwords and deactivations. Set `SUPPORTOPS_WEB_PORT` before starting to change the host port. The container worker uses the mock provider. The standalone local model worker remains separately documented in [jobs](jobs.md).

## Backup and isolated restore

Backups can contain private data. Store them outside version control with access restricted to authorized operators. The backup command refuses to overwrite an existing output file. Restore creates a new database named `restore_` followed by lowercase letters or digits. It refuses an existing database and does not replace the active application database. A failed restore leaves its newly created target for inspection.

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
python scripts/compose_backup.py --project supportops-app backup --output tmp/supportops-backup.dump
python scripts/compose_backup.py --project supportops-app restore --input tmp/supportops-backup.dump --database restore_example
```

The command requires a local Docker socket context and locates the single running database container using its exact Compose project and service labels. A restore into a new database does not switch the running application to that database. Plan and verify any cutover separately. Stop the stack using `docker compose -f compose.full.yaml down`. The volume persists. Removing volumes destroys data and should only be done deliberately for a verified disposable test project.

## Verified scope

See [stack evidence](evidence/2026-11-09-compose.md). The local synthetic stack, mock worker and isolated database restore were exercised. PostgreSQL uses a digest-pinned image. The Python, Node, nginx and uv base images use version tags, so future builds require renewed supply-chain and compatibility review. Cloud deployment, production secrets, external access, real-model container networking, recovery cutover, and production backup scheduling are not verified.
