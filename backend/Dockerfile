FROM ghcr.io/astral-sh/uv:0.12.10 AS uv
FROM python:3.14-slim
COPY --from=uv /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy PYTHONPATH=/app/backend/src
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/src ./src
ENV PATH=/opt/venv/bin:$PATH
CMD ["uvicorn", "supportops.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
