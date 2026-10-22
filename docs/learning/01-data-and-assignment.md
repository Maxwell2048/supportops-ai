# First exercise: Express business rules in data before optimizing queries

The design discussion established: requesters see only their tickets; messages are public or internal; authors come from trusted identity; reassignment preserves history; related writes commit together; versions prevent overwrites; idempotency prevents duplicate operations.

S05 implements storage before exposing business APIs, so S06 authentication and S07 assignment have a reliable foundation.

## Reading order

1. backend/src/supportops/models.py: start with User, Ticket, TicketEvent. Find requester_id, assignee_id, version, and changes.
2. backend/migrations/versions/0001_ticket_foundation.py: a versioned empty-database upgrade. Models describe the current target; migrations describe evolution. Editing a model does not update the database.
3. backend/tests/integration/test_database.py: read test_failed_event_insert_rolls_back_related_ticket_update.

## Rollback experiment

- Prepare an unassigned synthetic ticket at version 1.
- Inside a transaction savepoint, assign agent-a and set version 2.
- Try to insert an event with a nonexistent actor ID.
- The foreign key rejects it and the savepoint rolls back.
- Query again: assignee remains null, version remains 1, no event was added.

This demonstrates database transaction behavior, not a finished assignment service. The real service must also verify manager identity, current version, assignee role/active, and success audit. A savepoint isolates the experiment from other tests.

## Why two layers of validation?

A foreign key rejects a missing assignee ID. An existing user can still be a requester or inactive. The backend enforces cross-table business rules transactionally; future account disabling must follow the same lock protocol as assignment.

## Actual result

Written code and offline SQL are not database verification. On 2026-10-21 all 19 tests passed on real PostgreSQL with no skips; see [evidence](../evidence/2026-10-21-postgresql-verification.md).

From backend, run `uv run --locked python ../scripts/test_backend.py -v` to inspect names and outcomes. Deliberately breaking an event in an isolated test verifies that neither assignment nor version survives a partial failure.

Study question: why store actor_id as well as the old/new assignee in changes? Which different responsibilities do those three people represent?

References: [SQLAlchemy declarative tables](https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html). Read the project example first, then consult the matching concept.
