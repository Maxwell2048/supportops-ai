from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


SCHEMA_REVISION = "0010_job_tool_trace"


def make_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
        hide_parameters=True,
    )


def check_readiness(engine: Engine | None) -> tuple[bool, str]:
    if engine is None:
        return False, "database_not_configured"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revisions = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
            if revisions != {SCHEMA_REVISION}:
                return False, "database_schema_outdated"
    except SQLAlchemyError:
        # Driver exception text may contain addresses or secrets: never return it.
        return False, "database_unavailable_or_unmigrated"
    return True, "database_ready"
