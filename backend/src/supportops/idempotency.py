from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from supportops.errors import ApiError
from supportops.models import IdempotencyRecord


COLLECTION_ID = UUID(int=0)


@dataclass(frozen=True)
class WriteResult:
    status: int
    body: dict


def canonical_hash(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def claim(session: Session, actor_id: UUID, resource_id: UUID, operation: str, key: str, payload: BaseModel):
    digest = canonical_hash(payload.model_dump(mode="json", exclude_unset=True))
    scope = dict(actor_id=actor_id, resource_id=resource_id, operation=operation, key=key)
    # A concurrent duplicate waits at the unique index. A rolled-back claim disappears.
    inserted = session.execute(insert(IdempotencyRecord).values(**scope, request_hash=digest)
        .on_conflict_do_nothing(constraint="uq_idempotency_scope").returning(IdempotencyRecord.id)).scalar_one_or_none()
    record = session.scalar(select(IdempotencyRecord).filter_by(**scope).execution_options(populate_existing=True))
    if record.request_hash != digest:
        raise ApiError(409, "idempotency_conflict", "An idempotency key cannot be reused with different request content")
    if inserted is None:
        if record.response_status is None or record.response_body is None:
            raise ApiError(409, "idempotency_incomplete", "The operation result is not ready; retry later with the original idempotency key")
        return record, WriteResult(record.response_status, record.response_body)
    return record, None


def finish(session: Session, record: IdempotencyRecord, status: int, response: BaseModel) -> WriteResult:
    body = response.model_dump(mode="json")
    record.response_status = status
    record.response_body = body
    session.flush()
    return WriteResult(status, body)
