from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.models import Base

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

target_metadata = Base.metadata
# Aceleași opțiuni ca în `tests/test_models_schema.py`: autogenerate vede și schimbările de tip
# și de valoare implicită.
COMPARE_OPTIONS = {"compare_type": True, "compare_server_default": True}


def run_migrations_offline() -> None:
    """Scrie SQL-ul migrărilor fără conexiune la bază (`alembic upgrade head --sql`)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplică migrările pe baza din `RRM_DATABASE_URL`, aceeași pe care o folosește aplicația."""
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, **COMPARE_OPTIONS
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
