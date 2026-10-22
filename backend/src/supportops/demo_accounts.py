"""Explicit local activation; reseeding never reactivates a stopped account."""

from sqlalchemy.orm import Session

from supportops.models import User
from supportops.security import hash_password
from supportops.seed import synthetic_id


DEMO_ROLES = {
    "requester-a": "requester", "requester-b": "requester",
    "agent-a": "agent", "agent-b": "agent", "manager": "manager",
}


def activate_demo_accounts(session: Session, password: str) -> int:
    if not 12 <= len(password) <= 128:
        raise ValueError("DEMO_PASSWORD must contain 12 to 128 characters")
    changed = 0
    for label, role in DEMO_ROLES.items():
        user = session.get(User, synthetic_id(label), with_for_update=True)
        if user is None or user.email != f"{label}@example.invalid" or user.role != role:
            raise ValueError("Synthetic account identity mismatch; run seed and inspect local data")
        # Do not reset a password, undo manual deactivation, or change a role.
        if user.password_hash != "!login-disabled-until-S06" or user.active:
            continue
        user.password_hash = hash_password(password)
        user.active = True
        changed += 1
    return changed
