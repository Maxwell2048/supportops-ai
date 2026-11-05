from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints

from supportops.knowledge_schemas import KnowledgeChange
from supportops.schemas import DTO, postgres_text


class IndexCreate(KnowledgeChange):
    mode: Literal["keyword", "vector"] = "keyword"


class IndexResponse(DTO):
    version_id: UUID
    representation: str
    chunk_count: int
    mode: Literal["keyword", "vector"]
    profile_id: UUID | None
    provider: str | None


class SearchQuery(DTO):
    q: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500), AfterValidator(postgres_text)]
    mode: Literal["keyword", "vector"] = "keyword"
    limit: int = Field(default=5, ge=1, le=20)


class SearchHit(DTO):
    article_id: UUID
    version_id: UUID
    chunk_id: UUID
    ordinal: int
    start_offset: int
    end_offset: int
    text: str
    title: str
    content_hash: str
    version_hash: str
    source_kind: str
    source_reference: str
    license_note: str
    score: float


class SearchResponse(DTO):
    mode: Literal["keyword", "vector"]
    score_kind: str
    chunker: str
    profile_id: UUID | None
    provider: str | None
    available_versions: int
    indexed_versions: int
    items: list[SearchHit]
