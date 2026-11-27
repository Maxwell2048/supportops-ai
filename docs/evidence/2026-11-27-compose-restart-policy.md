# Compose restart policy for the database and web services (2026-11-27)

## Observed failure

A local `supportops-app` stack created from `compose.full.yaml` stopped working after the Docker engine stopped on 2026-11-21. Every container exited with code 255. When the engine came back, only `api` and `worker` restarted, because only they had `restart: unless-stopped`:

- `db` and `web` stayed in `Exited (255)`;
- `api` stayed up but `/ready` returned 503 and its health check reported unhealthy;
- `worker` restarted 338 times with `failed to resolve host 'db'`, because a stopped container's DNS alias is not resolvable;
- the web port answered nothing.

Starting `db` and `web` again, then restarting `api`, restored the stack without touching the data volume. Login as the synthetic manager account and a ticket list request succeeded afterwards.

## Change

`db` and `web` now use `restart: unless-stopped`, like `api` and `worker`. The one-shot `migrate` service keeps no restart policy. [Compose](../compose.md) documents the policy and how to apply it to a stack created from the older file.

## Verification

All on 2026-11-27, with Docker Desktop on Windows:

- `docker compose -f compose.full.yaml config` renders `unless-stopped` for `db`, `api`, `worker` and `web`, and none for `migrate`.
- A disposable project `supportops-restartcheck` (web port 18094, a throwaway env file outside the repository) was built from this branch and reached healthy with `up --build -d --wait`. `docker inspect` showed the same policies on the created containers.
- PostgreSQL fast shutdown (`kill -INT 1` inside `db`) made the container exit; Docker restarted it (restart count 1) and it became healthy again within about a second. `/ready` returned 200 afterwards and the worker did not restart.
- `nginx -s stop` inside `web` made it exit; Docker restarted it and `/` returned 200.
- The disposable project's containers, volume and locally built images were removed afterwards.
- The existing local `supportops-app` containers were given the same policy with `docker update --restart unless-stopped`.

A first attempt with `kill -TERM 1` only started a PostgreSQL smart shutdown, which waits for the API's pooled connections, so the process did not exit; that run is not counted as evidence.

## Limits

A real Docker engine or host restart was not repeated; the engine-restart behavior relies on Docker's documented `unless-stopped` semantics plus the process-exit restarts above. Start order after an engine restart is not governed by `depends_on`, so the API and worker may briefly fail until the database is healthy; they recover through their own restart policies and readiness check. The database-only `compose.yaml` was not changed.
