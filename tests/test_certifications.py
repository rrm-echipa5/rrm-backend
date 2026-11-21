from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# Utilizatorii din datele de test (db/seed.sql).
STUDENT_ANA = 3  # certificată pentru SEM (nivel 2) și Raman (nivel 1)
ADMIN_MIHAI = 4  # a acordat toate certificările, dar nu are niciuna
STUDENT_IOANA = 5  # certificată pentru SEM; certificarea pentru TEM e revocată

MY_CERTIFICATIONS = "/api/users/me/certifications"


def test_my_certifications_have_the_contract_shape(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    response = client.get(MY_CERTIFICATIONS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [cert["resource"] for cert in body] == [
        {"id": 7, "name": "Microscop electronic SEM"},
        {"id": 12, "name": "Spectrometru Raman"},
    ]
    sem = body[0]
    assert set(sem) == {
        "id",
        "user",
        "resource",
        "level",
        "status",
        "grantedAt",
        "grantedBy",
        "expiresAt",
        "revokedAt",
        "revokeReason",
    }
    assert sem["user"] == {
        "id": STUDENT_ANA,
        "name": "Ana Popescu",
        "email": "ana.popescu@student.usv.ro",
    }
    assert sem["grantedBy"]["name"] == "Mihai Ionescu"
    assert sem["level"] == 2
    assert sem["status"] == "ACTIVE"
    assert sem["expiresAt"] == "2027-10-31"
    assert sem["revokedAt"] is None


def test_my_certifications_include_the_revoked_ones(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_IOANA)
    body = client.get(MY_CERTIFICATIONS).json()

    assert [(cert["resource"]["id"], cert["status"]) for cert in body] == [
        (7, "ACTIVE"),
        (9, "REVOKED"),
    ]
    assert body[1]["revokeReason"] == "Nu a respectat procedura de oprire a fasciculului."


def test_an_expired_certification_has_status_expired(
    client: TestClient, as_user: Callable[[int], None], db_session: Session
) -> None:
    db_session.execute(
        text(
            "UPDATE certifications SET expires_at = current_date - 1"
            " WHERE user_id = :user_id AND resource_id = 12"
        ),
        {"user_id": STUDENT_ANA},
    )
    as_user(STUDENT_ANA)
    body = client.get(MY_CERTIFICATIONS).json()

    assert [cert["status"] for cert in body] == ["ACTIVE", "EXPIRED"]


def test_the_active_certification_comes_before_the_revoked_one_for_the_same_resource(
    client: TestClient, as_user: Callable[[int], None], db_session: Session
) -> None:
    db_session.execute(
        text(
            "INSERT INTO certifications (user_id, resource_id, level, granted_by)"
            " VALUES (5, 9, 2, 4)"
        )
    )
    as_user(STUDENT_IOANA)
    body = client.get(MY_CERTIFICATIONS).json()

    assert [(cert["resource"]["id"], cert["status"]) for cert in body] == [
        (7, "ACTIVE"),
        (9, "ACTIVE"),
        (9, "REVOKED"),
    ]


def test_a_user_without_certifications_gets_an_empty_list(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(ADMIN_MIHAI)
    response = client.get(MY_CERTIFICATIONS)

    assert response.status_code == 200, response.text
    assert response.json() == []
