from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic import command
from alembic.config import Config
from pathlib import Path
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from supportops.db import SCHEMA_REVISION, check_readiness
from supportops.models import Base, Ticket, TicketEvent, TicketMessage, User
from supportops.seed import seed, synthetic_id


pytestmark = pytest.mark.integration


def test_migrated_schema_matches_models_and_is_ready(pg_engine):
    with pg_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    assert check_readiness(pg_engine) == (True, "database_ready")


def test_migration_roundtrip_in_isolated_test_schema(pg_engine):
    with pg_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata)
        command.upgrade(config, "head")
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


@pytest.mark.parametrize('previous', ['0001_ticket_foundation', '0002_ticket_idempotency'])
def test_upgrade_from_previous_revision_preserves_existing_seed_records(pg_engine, previous):
    with pg_engine.connect() as connection:
        outer = connection.begin()
        try:
            config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.downgrade(config, previous)
            from sqlalchemy.orm import Session
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                seed(session)
                session.commit()
            before = connection.execute(select(Ticket.id, Ticket.title, Ticket.version)).all()
            command.upgrade(config, "head")
            assert connection.execute(select(Ticket.id, Ticket.title, Ticket.version)).all() == before
            assert connection.scalar(select(func.count()).select_from(User)) == 5
            assert connection.scalar(select(func.count()).select_from(TicketEvent)) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_REVISION
        finally:
            outer.rollback()


def test_readiness_rejects_stale_schema_revision(pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'old_revision'"))
    try:
        assert check_readiness(pg_engine) == (False, "database_schema_outdated")
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :version"), {"version": SCHEMA_REVISION})


def test_seed_can_repeat_without_resetting_existing_data(db_session):
    seed(db_session)
    db_session.flush()
    ticket = db_session.get(Ticket, synthetic_id("ticket-1"))
    ticket.title = "Updated synthetic title"
    db_session.flush()
    seed(db_session)
    db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(User)) == 5
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 1
    assert db_session.scalar(select(func.count()).select_from(TicketEvent)) == 1
    db_session.refresh(ticket)
    assert ticket.title == "Updated synthetic title"
    assert db_session.scalar(select(func.count()).select_from(User).where(User.active)) == 0
    assert ticket.created_at.utcoffset() is not None


@pytest.mark.parametrize("changes", [
    {"requester_id": uuid4()}, {"status": "unknown"}, {"version": 0},
    {"priority": "critical"}, {"title": "   "}, {"body": ""},
    {"archived": True}, {"status": "in_progress", "assignee_id": None},
])
def test_database_rejects_invalid_ticket_state(db_session, changes):
    seed(db_session)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(**changes))


def test_message_author_must_exist(db_session):
    seed(db_session)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(TicketMessage(ticket_id=synthetic_id("ticket-1"), author_id=uuid4(), visibility="public", body="Synthetic reply"))
        db_session.flush()


def test_failed_event_insert_rolls_back_related_ticket_update(db_session):
    seed(db_session)
    db_session.flush()
    ticket_id = synthetic_id("ticket-1")
    # Exercise a database transaction, not a not-yet-implemented assignment service.
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(update(Ticket).where(Ticket.id == ticket_id).values(assignee_id=synthetic_id("agent-a"), version=2))
        db_session.add(TicketEvent(ticket_id=ticket_id, actor_id=uuid4(), event_type="assigned", changes={}, ticket_version=2))
        db_session.flush()
    db_session.expire_all()
    ticket = db_session.get(Ticket, ticket_id)
    assert ticket.assignee_id is None
    assert ticket.version == 1
    assert db_session.scalar(select(func.count()).select_from(TicketEvent)) == 1
