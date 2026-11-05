from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from supportops import knowledge_service as service
from supportops.dependencies import CurrentUser, DbSession
from supportops.knowledge_schemas import KnowledgeArticleResponse, KnowledgeChange, KnowledgeCreate, KnowledgeEventPage, KnowledgePage, KnowledgeQuery, KnowledgeVersionResponse
from supportops.retrieval_schemas import IndexCreate, IndexResponse, SearchQuery, SearchResponse
from supportops import retrieval

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.get("/search", response_model=SearchResponse)
def search(request: Request, user: CurrentUser, session: DbSession, query: Annotated[SearchQuery, Query()]):
    return retrieval.search(session, user, query, request.app.state.embedding_provider)


@router.post("/articles/{article_id}/index", response_model=IndexResponse)
def index(article_id: UUID, payload: IndexCreate, request: Request, user: CurrentUser, session: DbSession, key: Key):
    session.info["request_id"] = UUID(request.state.request_id)
    return commit(session, retrieval.build_index(session, user.id, article_id, payload, key, request.app.state.embedding_provider))


def commit(session, result):
    response = JSONResponse(status_code=result.status, content=result.body)
    session.commit()
    return response


@router.post("/articles", response_model=KnowledgeArticleResponse, status_code=201)
def create(payload: KnowledgeCreate, request: Request, user: CurrentUser, session: DbSession, key: Key):
    session.info["request_id"] = UUID(request.state.request_id)
    return commit(session, service.create_draft(session, user.id, payload, key))


@router.post("/articles/{article_id}/publish", response_model=KnowledgeArticleResponse)
def publish(article_id: UUID, payload: KnowledgeChange, request: Request, user: CurrentUser, session: DbSession, key: Key):
    session.info["request_id"] = UUID(request.state.request_id)
    return commit(session, service.change_publication(session, user.id, article_id, payload, key))


@router.post("/articles/{article_id}/archive", response_model=KnowledgeArticleResponse)
def archive(article_id: UUID, payload: KnowledgeChange, request: Request, user: CurrentUser, session: DbSession, key: Key):
    session.info["request_id"] = UUID(request.state.request_id)
    return commit(session, service.change_publication(session, user.id, article_id, payload, key, archive=True))


@router.get("/articles", response_model=KnowledgePage)
def articles(request: Request, user: CurrentUser, session: DbSession, query: Annotated[KnowledgeQuery, Query()]):
    return service.list_knowledge(session, user, query, request.app.state.settings)


@router.get("/articles/{article_id}", response_model=KnowledgeArticleResponse, response_model_exclude_none=True)
def article(article_id: UUID, user: CurrentUser, session: DbSession):
    return service.read_article(session, user, article_id)


@router.get("/versions/{version_id}", response_model=KnowledgeVersionResponse)
def version(version_id: UUID, user: CurrentUser, session: DbSession):
    return service.read_version(session, user, version_id)


@router.get("/articles/{article_id}/versions", response_model=KnowledgePage)
def versions(article_id: UUID, request: Request, user: CurrentUser, session: DbSession, query: Annotated[KnowledgeQuery, Query()]):
    return service.list_knowledge(session, user, query, request.app.state.settings, article_id)


@router.get("/articles/{article_id}/events", response_model=KnowledgeEventPage)
def events(article_id: UUID, request: Request, user: CurrentUser, session: DbSession, query: Annotated[KnowledgeQuery, Query()]):
    return service.list_events(session, user, article_id, query, request.app.state.settings)
