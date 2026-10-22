"""Repeatable synthetic data. New accounts start disabled; existing states persist."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from supportops.config import load_settings
from supportops.db import check_readiness, make_engine
from supportops.models import Ticket, TicketEvent, User


def synthetic_id(label: str):
    return uuid5(NAMESPACE_URL, f"supportops.synthetic/{label}")


def seed(session: Session) -> None:
    """Add missing known IDs only. Caller owns transaction; never reset existing data."""
    for label, role in [
        ("requester-a", "requester"), ("requester-b", "requester"),
        ("agent-a", "agent"), ("agent-b", "agent"), ("manager", "manager"),
    ]:
        session.execute(insert(User).values(
            id=synthetic_id(label), email=f"{label}@example.invalid",
            role=role, active=False, password_hash="!login-disabled-until-S06",
        ).on_conflict_do_nothing(index_elements=[User.id]))
    ticket_id = synthetic_id("ticket-1")
    inserted = session.execute(insert(Ticket).values(
        id=ticket_id, requester_id=synthetic_id("requester-a"),
        title="Cannot sign in to the sample product", body="Synthetic case: the account is reported as locked after entering a password.",
    ).on_conflict_do_nothing(index_elements=[Ticket.id]).returning(Ticket.id)).scalar_one_or_none()
    if inserted is not None:
        session.add(TicketEvent(
            id=synthetic_id("ticket-1-created"), ticket_id=ticket_id,
            actor_id=synthetic_id("requester-a"), event_type="created",
            changes={"status": {"from": None, "to": "open"}}, ticket_version=1,
        ))


def main() -> None:
    url = load_settings().database_url
    if not url:
        raise SystemExit("Configure local .env or DATABASE_URL first")
    engine = make_engine(url)
    try:
        ready, reason = check_readiness(engine)
        if not ready:
            raise SystemExit(f"Cannot seed: {reason}. Run alembic upgrade head first.")
        with Session(engine) as session, session.begin():
            seed(session)
        print("Synthetic foundation seed complete; missing rows inserted, existing account states and records preserved.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
