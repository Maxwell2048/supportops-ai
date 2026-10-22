# ADR 0002: Database foundation and isolated integration tests

Date: 2026-10-21. Status: accepted. Subsequent real PostgreSQL verification: [evidence](../evidence/2026-10-21-postgresql-verification.md).

- First migration contains users, tickets, ticket_messages, and ticket_events only. AI, knowledge, audit, and generic idempotency follow their stages.
- Pin SQLAlchemy 2.1.5, Alembic 1.20.0, psycopg[binary] 3.3.6, and python-dotenv 1.2.4 after PyPI verification; update uv.lock.
- Use synchronous SQLAlchemy. Synchronous FastAPI database handlers run in the thread pool rather than blocking an async event loop. A business request owns one transaction.
- Readiness checks connectivity and the expected revision, not just SELECT 1. Liveness works without configuration. Driver details never reach clients.
- Do not call metadata.create_all at startup. Historical migrations explicitly define their schema instead of importing mutable future models.
- Use random schemas inside a dedicated database ending in _test; clean only that schema, never public development tables. SQLite is not a PostgreSQL acceptance substitute.
- Seed accounts default disabled with a non-login sentinel; activate demo credentials only after S06 introduces proper hashing.
- Initial indexes follow known access paths, with no claimed performance benefit. S20 measures EXPLAIN and fixed data.
- Docker startup failure is an environment blocker; code, offline SQL, unit tests, and actual database verification are separate evidence.
