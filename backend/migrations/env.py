from alembic import context
from sqlalchemy import create_engine, pool

from supportops.config import load_settings
from supportops.models import Base


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    database_url = load_settings().database_url
    if not database_url:
        raise RuntimeError("Database not configured; set local .env or DATABASE_URL")
    context.configure(url=database_url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    migrate(context.config.attributes["connection"])
else:
    database_url = load_settings().database_url
    if not database_url:
        raise RuntimeError("Database not configured; set local .env or DATABASE_URL")
    engine = create_engine(database_url, poolclass=pool.NullPool, hide_parameters=True, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()
