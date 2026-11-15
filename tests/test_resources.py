import re
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app

SEM_ID = 7
TEM_ID = 9
HPC_ID = 10
ROOM_ID = 11
RAMAN_ID = 12
UNKNOWN_ID = 999_999
# Utilizatorii din datele de test (db/seed.sql).
SYSTEM_ADMIN_ELENA = 1
STUDENT_ANA = 3  # certificări valabile pentru SEM și Raman
STUDENT_IOANA = 5  # certificare valabilă pentru SEM, revocată pentru TEM
RESEARCHER_RADU = 6  # fără certificări în datele de test
ADMIN_MIHAI = 4  # utilizatorul implicit; administrează SEM, TEM și Raman
ADMIN_VLAD = 7  # administrează HPC și sala de seminar


@pytest.fixture
def as_user() -> Iterator[Callable[[int], None]]:
    """Face cererile în numele altui utilizator decât cel implicit (Mihai Ionescu, id 4)."""

    def switch(user_id: int) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(demo_user_id=user_id)

    yield switch
    app.dependency_overrides.pop(get_settings, None)


def new_resource(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Imprimantă 3D Prusa",
        "categoryId": 1,
        "location": "Corp C, sala C110",
        "description": "Imprimantă 3D cu filament PLA și PETG.",
        "specifications": {"Volum de lucru": "250 x 210 x 220 mm"},
        "tags": ["printare 3D", "prototipare"],
        "approvalFlow": "COORDINATOR",
    }
    body.update(overrides)
    return body


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/resources", json=new_resource(**overrides))
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def test_list_categories(client: TestClient) -> None:
    response = client.get("/api/resource-categories")

    assert response.status_code == 200
    assert [category["code"] for category in response.json()] == [
        "HARDWARE",
        "HPC",
        "ROOM",
        "MEASUREMENT_INSTRUMENT",
    ]


def test_list_resources_is_paginated_and_sorted_by_name(client: TestClient) -> None:
    response = client.get("/api/resources", params={"size": 2})

    body = response.json()
    assert response.status_code == 200
    assert [item["name"] for item in body["content"]] == [
        "Cluster HPC - nod GPU",
        "Microscop electronic SEM",
    ]
    assert body["page"] == {"page": 0, "size": 2, "totalElements": 5, "totalPages": 3}
    assert body["content"][0]["category"] == {"id": 2, "name": "Calcul de înaltă performanță"}
    assert body["content"][0]["approvalFlow"] == "AUTO"


def test_list_resources_filters_by_category_status_and_text(client: TestClient) -> None:
    by_category = client.get("/api/resources", params={"categoryId": 1}).json()
    by_text = client.get("/api/resources", params={"q": "raman"}).json()
    by_specification = client.get("/api/resources", params={"q": "L40S"}).json()
    by_status = client.get("/api/resources", params={"status": "FAULTY"}).json()

    assert {item["id"] for item in by_category["content"]} == {7, 9}
    assert [item["name"] for item in by_text["content"]] == ["Spectrometru Raman"]
    assert [item["id"] for item in by_specification["content"]] == [HPC_ID]
    assert by_status["content"] == []


def test_list_resources_sorts_descending(client: TestClient) -> None:
    body = client.get("/api/resources", params={"sort": "name,desc"}).json()

    assert body["content"][0]["name"] == "Spectrometru Raman"


def test_list_resources_rejects_invalid_parameters(client: TestClient) -> None:
    response = client.get("/api/resources", params={"size": 500, "sort": "parola,asc"})

    body = response.json()
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert body["code"] == "VALIDATION_FAILED"
    assert {error["field"] for error in body["errors"]} == {"size", "sort"}


def test_get_resource_detail(client: TestClient) -> None:
    response = client.get(f"/api/resources/{SEM_ID}")

    body = response.json()
    assert response.status_code == 200
    assert body["name"] == "Microscop electronic SEM"
    assert body["specifications"]["Detector"] == "EDS Oxford Ultim Max 65"
    assert body["administrator"]["name"] == "Mihai Ionescu"
    assert body["checkInQrCode"] == "RRM-R7-6f1c2a"


def test_check_in_qr_code_is_visible_only_to_the_resource_administrator(
    client: TestClient,
) -> None:
    body = client.get(f"/api/resources/{HPC_ID}").json()

    assert body["administrator"]["name"] == "Vlad Popa"
    assert body["checkInQrCode"] is None


def test_get_unknown_resource_returns_404_problem(client: TestClient) -> None:
    response = client.get(f"/api/resources/{UNKNOWN_ID}")

    body = response.json()
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert body["code"] == "NOT_FOUND"
    assert body["detail"] == f"Resursa {UNKNOWN_ID} nu există."
    assert body["instance"] == f"/api/resources/{UNKNOWN_ID}"


def test_create_resource(client: TestClient) -> None:
    response = client.post("/api/resources", json=new_resource())

    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"].endswith(f"/api/resources/{body['id']}")
    assert body["status"] == "ACTIVE"
    assert body["administrator"]["id"] == 4
    assert re.fullmatch(rf"RRM-R{body['id']}-[0-9a-f]{{6}}", body["checkInQrCode"])
    catalog = client.get("/api/resources", params={"q": "Prusa"}).json()
    assert [item["id"] for item in catalog["content"]] == [body["id"]]


def test_create_resource_with_explicit_administrator(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(SYSTEM_ADMIN_ELENA)

    body = create(client, administratorId=ADMIN_VLAD)

    assert body["administrator"]["name"] == "Vlad Popa"
    assert body["checkInQrCode"] is None


def test_create_resource_validates_fields(client: TestClient) -> None:
    response = client.post(
        "/api/resources",
        json={"name": "A", "categoryId": 1, "tags": ["x" * 41], "approvalFlow": "MANUAL"},
    )

    body = response.json()
    assert response.status_code == 400
    assert body["code"] == "VALIDATION_FAILED"
    errors = {error["field"]: error["message"] for error in body["errors"]}
    assert errors["name"] == "Textul trebuie să aibă cel puțin 2 caractere."
    assert errors["tags.0"] == "Textul poate avea cel mult 40 caractere."
    assert errors["approvalFlow"].startswith("Valoarea nu este permisă.")


def test_create_resource_rejects_unknown_category_and_administrator(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(SYSTEM_ADMIN_ELENA)

    response = client.post(
        "/api/resources", json=new_resource(categoryId=UNKNOWN_ID, administratorId=UNKNOWN_ID)
    )

    body = response.json()
    assert response.status_code == 400
    assert {error["field"] for error in body["errors"]} == {"categoryId", "administratorId"}


def test_update_resource(client: TestClient) -> None:
    created = create(client)

    response = client.put(
        f"/api/resources/{created['id']}",
        json=new_resource(name="Imprimantă 3D Prusa MK4", tags=["printare 3D"], categoryId=4),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["name"] == "Imprimantă 3D Prusa MK4"
    assert body["tags"] == ["printare 3D"]
    assert body["category"]["id"] == 4
    assert body["checkInQrCode"] == created["checkInQrCode"]
    assert body["updatedAt"] >= created["updatedAt"]


def test_update_unknown_resource_returns_404(client: TestClient) -> None:
    response = client.put(f"/api/resources/{UNKNOWN_ID}", json=new_resource())

    assert response.status_code == 404


def test_delete_resource(client: TestClient, as_user: Callable[[int], None]) -> None:
    created = create(client)
    as_user(SYSTEM_ADMIN_ELENA)

    response = client.delete(f"/api/resources/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/resources/{created['id']}").status_code == 404
    catalog = client.get("/api/resources", params={"q": "Prusa"}).json()
    assert catalog["content"] == []


def test_delete_resource_with_future_reservation_returns_409(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    created = create(client, approvalFlow="AUTO")
    db_session.execute(
        text(
            """
            INSERT INTO reservations (resource_id, requester_id, project_id, start_at, end_at,
                                      purpose, status, approval_flow, check_in_deadline)
            VALUES (:resource_id, 3, 1, now() + interval '1 day', now() + interval '1 day 2 hours',
                    'Test', 'CONFIRMED', 'AUTO', now() + interval '1 day 15 minutes')
            """
        ),
        {"resource_id": created["id"]},
    )
    as_user(SYSTEM_ADMIN_ELENA)

    response = client.delete(f"/api/resources/{created['id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_HAS_RESERVATIONS"
    assert client.get(f"/api/resources/{created['id']}").status_code == 200


def test_delete_unknown_resource_returns_404(client: TestClient) -> None:
    assert client.delete(f"/api/resources/{UNKNOWN_ID}").status_code == 404


def test_list_resources_filters_by_all_requested_tags(client: TestClient) -> None:
    one_tag = client.get("/api/resources", params={"tag": "microscopie"}).json()
    two_tags = client.get("/api/resources", params={"tag": ["hpc", "gpu"]}).json()
    no_match = client.get("/api/resources", params={"tag": ["hpc", "microscopie"]}).json()

    assert {item["id"] for item in one_tag["content"]} == {SEM_ID, TEM_ID}
    assert [item["id"] for item in two_tags["content"]] == [HPC_ID]
    assert no_match["content"] == []
    assert no_match["page"]["totalElements"] == 0


def test_list_resources_filters_by_administered_by_me(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    by_mihai = client.get("/api/resources", params={"administeredByMe": "true"}).json()
    as_user(ADMIN_VLAD)
    by_vlad = client.get("/api/resources", params={"administeredByMe": "true"}).json()
    everything = client.get("/api/resources", params={"administeredByMe": "false"}).json()

    assert {item["id"] for item in by_mihai["content"]} == {SEM_ID, TEM_ID, RAMAN_ID}
    assert {item["id"] for item in by_vlad["content"]} == {HPC_ID, ROOM_ID}
    assert everything["page"]["totalElements"] == 5


def test_list_resources_combines_tag_and_administrator_filters(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(ADMIN_VLAD)
    body = client.get(
        "/api/resources", params={"tag": "microscopie", "administeredByMe": "true"}
    ).json()

    assert body["content"] == []


def test_user_certified_for_a_certified_user(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    catalog = client.get("/api/resources").json()

    certified = {item["id"]: item["userCertified"] for item in catalog["content"]}
    assert certified == {
        SEM_ID: True,
        TEM_ID: False,
        HPC_ID: False,
        ROOM_ID: False,
        RAMAN_ID: True,
    }
    assert client.get(f"/api/resources/{SEM_ID}").json()["userCertified"] is True


def test_user_certified_is_false_for_a_user_without_certifications(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(RESEARCHER_RADU)
    catalog = client.get("/api/resources").json()

    assert all(item["userCertified"] is False for item in catalog["content"])
    assert client.get(f"/api/resources/{SEM_ID}").json()["userCertified"] is False


def test_user_certified_is_false_for_an_expired_certification(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    db_session.execute(
        text(
            """
            INSERT INTO certifications (user_id, resource_id, level, granted_by, expires_at)
            VALUES (:user_id, :resource_id, 1, 7, current_date - 1)
            """
        ),
        {"user_id": RESEARCHER_RADU, "resource_id": HPC_ID},
    )
    as_user(RESEARCHER_RADU)

    body = client.get(f"/api/resources/{HPC_ID}").json()

    assert body["userCertified"] is False


def test_user_certified_is_false_for_a_revoked_certification(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_IOANA)
    catalog = client.get("/api/resources", params={"tag": "microscopie"}).json()

    certified = {item["id"]: item["userCertified"] for item in catalog["content"]}
    assert certified == {SEM_ID: True, TEM_ID: False}


def test_list_resources_rejects_too_many_tags(client: TestClient) -> None:
    response = client.get("/api/resources", params={"tag": [f"t{i}" for i in range(21)]})

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_FAILED"


def test_list_resources_rejects_invalid_administered_by_me(client: TestClient) -> None:
    response = client.get("/api/resources", params={"administeredByMe": "poate"})

    body = response.json()
    assert response.status_code == 400
    assert body["errors"] == [
        {"field": "administeredByMe", "message": "Valoarea trebuie să fie true sau false."}
    ]


def assert_access_denied(response: Any) -> None:
    assert response.status_code == 403, response.text
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "ACCESS_DENIED"


def test_create_resource_gets_default_usage_rules(client: TestClient) -> None:
    body = create(client)

    rule = body["usageRule"]
    assert rule["minDurationMinutes"] == 30
    assert rule["maxDurationMinutes"] == 240
    assert rule["breakBetweenMinutes"] == 0
    assert rule["checkInDeadlineMinutes"] == 15
    assert rule["requiredCertificationLevel"] is None
    assert rule["approvalFlow"] == "COORDINATOR"
    assert rule["updatedBy"]["id"] == ADMIN_MIHAI
    assert client.get(f"/api/resources/{body['id']}").json()["usageRule"] == rule


def test_resource_detail_shows_usage_rules(client: TestClient) -> None:
    rule = client.get(f"/api/resources/{SEM_ID}").json()["usageRule"]

    assert rule["minDurationMinutes"] == 30
    assert rule["breakBetweenMinutes"] == 15
    assert rule["requiredCertificationLevel"] == 2
    assert rule["approvalFlow"] == "COORDINATOR_AND_ADMIN"
    assert rule["updatedBy"]["name"] == "Mihai Ionescu"


@pytest.mark.parametrize("user_id", [STUDENT_ANA, RESEARCHER_RADU])
def test_only_resource_admins_can_create_resources(
    client: TestClient, as_user: Callable[[int], None], user_id: int
) -> None:
    as_user(user_id)

    response = client.post("/api/resources", json=new_resource())

    assert_access_denied(response)
    as_user(SYSTEM_ADMIN_ELENA)
    catalog = client.get("/api/resources", params={"q": "Prusa"}).json()
    assert catalog["content"] == []


def test_system_admin_can_create_resources(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(SYSTEM_ADMIN_ELENA)

    body = create(client)

    assert body["administrator"]["id"] == SYSTEM_ADMIN_ELENA


def test_resource_admin_cannot_create_a_resource_for_another_administrator(
    client: TestClient,
) -> None:
    response = client.post("/api/resources", json=new_resource(administratorId=ADMIN_VLAD))

    assert_access_denied(response)


def test_resource_admin_can_name_themselves_as_administrator(client: TestClient) -> None:
    body = create(client, administratorId=ADMIN_MIHAI)

    assert body["administrator"]["id"] == ADMIN_MIHAI


@pytest.mark.parametrize("user_id", [ADMIN_VLAD, STUDENT_ANA])
def test_only_the_resource_administrator_can_update_it(
    client: TestClient, as_user: Callable[[int], None], user_id: int
) -> None:
    as_user(user_id)

    response = client.put(f"/api/resources/{SEM_ID}", json=new_resource())

    assert_access_denied(response)
    assert client.get(f"/api/resources/{SEM_ID}").json()["name"] == "Microscop electronic SEM"


def test_system_admin_can_update_any_resource_and_change_its_administrator(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(SYSTEM_ADMIN_ELENA)

    response = client.put(
        f"/api/resources/{SEM_ID}",
        json=new_resource(name="Microscop SEM", administratorId=ADMIN_VLAD),
    )

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["name"] == "Microscop SEM"
    assert body["administrator"]["id"] == ADMIN_VLAD


def test_resource_admin_cannot_change_the_administrator(client: TestClient) -> None:
    response = client.put(
        f"/api/resources/{SEM_ID}", json=new_resource(administratorId=ADMIN_VLAD)
    )

    assert_access_denied(response)
    administrator = client.get(f"/api/resources/{SEM_ID}").json()["administrator"]
    assert administrator["id"] == ADMIN_MIHAI


def test_update_keeps_usage_rules_and_shows_the_new_approval_flow(client: TestClient) -> None:
    response = client.put(f"/api/resources/{SEM_ID}", json=new_resource(approvalFlow="AUTO"))

    rule = response.json()["usageRule"]
    assert response.status_code == 200
    assert rule["approvalFlow"] == "AUTO"
    assert rule["requiredCertificationLevel"] == 2


@pytest.mark.parametrize("user_id", [ADMIN_MIHAI, STUDENT_ANA])
def test_only_system_admin_can_delete_resources(
    client: TestClient, as_user: Callable[[int], None], user_id: int
) -> None:
    as_user(user_id)

    response = client.delete(f"/api/resources/{RAMAN_ID}")

    assert_access_denied(response)
    assert client.get(f"/api/resources/{RAMAN_ID}").status_code == 200


def test_unknown_resource_returns_404_before_checking_rights(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)

    assert client.put(f"/api/resources/{UNKNOWN_ID}", json=new_resource()).status_code == 404
    assert client.delete(f"/api/resources/{UNKNOWN_ID}").status_code == 404
