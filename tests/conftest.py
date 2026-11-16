from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_engine, get_session
from app.main import app


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sesiune într-o tranzacție anulată la final, ca testele să nu modifice datele de test."""
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """Client HTTP pentru API, legat de sesiunea tranzacțională a testului."""

    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def as_user() -> Iterator[Callable[[int], None]]:
    """Face cererile în numele altui utilizator decât cel implicit (Mihai Ionescu, id 4)."""

    def switch(user_id: int) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(demo_user_id=user_id)

    yield switch
    app.dependency_overrides.pop(get_settings, None)
