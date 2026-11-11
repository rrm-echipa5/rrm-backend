import re
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

SEM_ID = 7
HPC_ID = 10
UNKNOWN_ID = 999_999


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


def test_create_resource_with_explicit_administrator(client: TestClient) -> None:
    body = create(client, administratorId=7)

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


def test_create_resource_rejects_unknown_category_and_administrator(client: TestClient) -> None:
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


def test_delete_resource(client: TestClient) -> None:
    created = create(client)

    response = client.delete(f"/api/resources/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/resources/{created['id']}").status_code == 404
    catalog = client.get("/api/resources", params={"q": "Prusa"}).json()
    assert catalog["content"] == []


def test_delete_resource_with_future_reservation_returns_409(
    client: TestClient, db_session: Session
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

    response = client.delete(f"/api/resources/{created['id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_HAS_RESERVATIONS"
    assert client.get(f"/api/resources/{created['id']}").status_code == 200


def test_delete_unknown_resource_returns_404(client: TestClient) -> None:
    assert client.delete(f"/api/resources/{UNKNOWN_ID}").status_code == 404
