from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, StrictInt, StringConstraints, model_validator

from supportops.schemas import DTO, postgres_text

Scope = Literal["support", "management"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), AfterValidator(postgres_text)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50000), AfterValidator(postgres_text)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000), AfterValidator(postgres_text)]
License = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000), AfterValidator(postgres_text)]
Revision = Annotated[StrictInt, Field(gt=0, le=2147483647)]


class KnowledgeCreate(DTO):
    article_id: UUID | None = None
    expected_revision: Revision | None = None
    title: Title
    body: Body
    scope: Scope
    source_kind: Literal["synthetic", "licensed"]
    source_reference: Reference
    license_note: License

    @model_validator(mode="after")
    def revision_pair(self):
        if (self.article_id is None) != (self.expected_revision is None):
            raise ValueError("Existing articles require expected_revision; new articles must omit it")
        return self


class KnowledgeChange(DTO):
    version_id: UUID
    expected_revision: Revision


class KnowledgeQuery(DTO):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)


class KnowledgeVersionResponse(DTO):
    id: UUID
    article_id: UUID
    number: int
    title: str
    body: str
    scope: Scope
    source_kind: Literal["synthetic", "licensed"]
    source_reference: str
    license_note: str
    content_hash: str
    created_by: UUID
    created_at: datetime
    status: Literal["draft", "published", "archived"]


class KnowledgeArticleResponse(DTO):
    id: UUID
    revision: int | None = None
    published_version_id: UUID | None
    archived: bool
    version: KnowledgeVersionResponse


class KnowledgeSummary(DTO):
    article_id: UUID
    version_id: UUID
    number: int
    title: str
    scope: Scope
    status: Literal["draft", "published", "archived"]


class KnowledgePage(DTO):
    items: list[KnowledgeSummary]
    next_cursor: str | None


class KnowledgeEventResponse(DTO):
    id: UUID
    article_id: UUID
    version_id: UUID
    article_revision: int
    actor_id: UUID
    actor_role: Literal["manager"]
    action: Literal["draft_created", "published", "archived"]
    result: Literal["success"]
    request_id: UUID
    changes: dict
    created_at: datetime


class KnowledgeEventPage(DTO):
    items: list[KnowledgeEventResponse]
    next_cursor: str | None
