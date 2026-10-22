from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StringConstraints, field_validator, model_validator


def postgres_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Null characters are not supported")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must be valid UTF-8") from None
    return value


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class LoginInput(DTO):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def email_characters(cls, value):
        return postgres_text(value)

    @field_validator("password")
    @classmethod
    def password_characters(cls, value):
        postgres_text(value.get_secret_value())
        return value


class TokenResponse(DTO):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserResponse(DTO):
    id: UUID
    email: str
    role: Literal["requester", "agent", "manager"]


class MessageResponse(DTO):
    id: UUID
    author_id: UUID
    visibility: Literal["public", "internal"]
    body: str
    created_at: datetime


class EventResponse(DTO):
    id: UUID
    actor_id: UUID
    event_type: str
    changes: dict
    ticket_version: int
    created_at: datetime


class TicketSummary(DTO):
    id: UUID
    requester_id: UUID
    assignee_id: UUID | None
    title: str
    body: str
    status: str
    priority: str
    version: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class TicketResponse(TicketSummary):
    messages: list[MessageResponse]


class StaffTicketResponse(TicketResponse):
    events: list[EventResponse]


TicketStatus = Literal["open", "in_progress", "waiting_customer", "resolved", "closed"]
TicketPriority = Literal["low", "normal", "high", "urgent"]
BodyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000), AfterValidator(postgres_text)]
ReasonText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000), AfterValidator(postgres_text)]


class TicketCreate(DTO):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), AfterValidator(postgres_text)]
    body: BodyText


class TicketPatch(DTO):
    expected_version: StrictInt = Field(gt=0, le=2147483647)
    status: TicketStatus | None = None
    assignee_id: UUID | None = None
    priority: TicketPriority | None = None
    archived: StrictBool | None = None
    reason: ReasonText | None = None
    public_reply: BodyText | None = None

    @model_validator(mode="after")
    def explicit_nulls(self):
        for name in ("status", "priority", "archived"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class MessageCreate(DTO):
    expected_version: StrictInt = Field(gt=0, le=2147483647)
    visibility: Literal["public", "internal"]
    body: BodyText


class MessageWriteResponse(DTO):
    message: MessageResponse
    ticket_version: int


class TicketQuery(DTO):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: UUID | None = None
    q: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), AfterValidator(postgres_text)] | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)
    limit: int = Field(default=20, ge=1, le=100)


class TicketPage(DTO):
    items: list[TicketSummary]
    next_cursor: str | None


AuditAction = Literal['ticket.created', 'ticket.assigned', 'ticket.updated', 'ticket.message_added']


class AuditQuery(DTO):
    resource_type: Literal['ticket'] = 'ticket'
    resource_id: UUID | None = None
    actor_id: UUID | None = None
    request_id: UUID | None = None
    action: AuditAction | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)
    limit: int = Field(default=20, ge=1, le=100)


class AuditResponse(DTO):
    id: UUID
    actor_id: UUID
    actor_role: Literal['requester', 'agent', 'manager']
    resource_type: Literal['ticket']
    resource_id: UUID
    action: AuditAction
    result: Literal['success']
    request_id: UUID
    ticket_version: int
    changes: dict
    created_at: datetime


class AuditPage(DTO):
    items: list[AuditResponse]
    next_cursor: str | None
