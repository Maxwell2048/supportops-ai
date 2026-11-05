from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import Engine

from supportops.config import Settings, load_settings
from supportops.db import check_readiness, make_engine
from supportops.errors import install_error_handlers
from supportops.rate_limit import LoginLimiter
from supportops.routes import router
from supportops.knowledge_routes import router as knowledge_router


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    reason: str


def create_app(settings: Settings | None = None, *, engine: Engine | None = None, embedding_provider=None) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    owns_engine = engine is None
    engine = engine if engine is not None else (make_engine(settings.database_url) if settings.database_url else None)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if engine is not None and owns_engine:
            engine.dispose()

    app = FastAPI(title="SupportOps AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.login_limiter = LoginLimiter()
    from supportops.embeddings import OllamaEmbedding
    app.state.embedding_provider = embedding_provider if embedding_provider is not None else OllamaEmbedding(settings.embedding_url)
    install_error_handlers(app)
    app.include_router(router)
    app.include_router(knowledge_router)

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="supportops-api")

    @app.get("/ready", response_model=ReadinessResponse, tags=["operations"])
    def ready(response: Response) -> ReadinessResponse:
        is_ready, reason = check_readiness(engine)
        if is_ready and not settings.jwt_secret:
            is_ready, reason = False, "auth_not_configured"
        response.status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="ready" if is_ready else "not_ready", reason=reason)

    return app


app = create_app()
