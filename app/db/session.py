from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Creează o singură dată conexiunea la PostgreSQL, din `RRM_DATABASE_URL`."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Întoarce fabrica de sesiuni SQLAlchemy legată de conexiunea aplicației."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependența FastAPI care deschide o sesiune pe cerere și o închide la final."""
    with get_session_factory()() as session:
        yield session


def is_database_available(session: Session) -> bool:
    """Verifică dacă baza de date răspunde și conține schema aplicației."""
    try:
        session.execute(text("SELECT 1 FROM resource_categories LIMIT 1"))
    except SQLAlchemyError:
        return False
    return True
