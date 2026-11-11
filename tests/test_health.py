from collections.abc import Iterator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_session
from app.main import app

client = TestClient(app)


def test_health_reports_database_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_unavailable() -> None:
    def broken_session() -> Iterator[MagicMock]:
        session = MagicMock()
        session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("conexiune"))
        yield session

    app.dependency_overrides[get_session] = broken_session
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.json() == {"status": "ok", "database": "unavailable"}
