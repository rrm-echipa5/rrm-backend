from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

# Utilizatorii din datele de test (db/seed.sql).
SYSTEM_ADMIN_ELENA = 1
COORDINATOR_ANDREI = 2  # coordonează echipa 1 (proiectele 1 și 2)
STUDENT_ANA = 3  # rezervările 1040, 1041, 1042, 1044, 1047
ADMIN_MIHAI = 4  # administrează SEM (resursa rezervării 1042)
STUDENT_IOANA = 5  # membră în echipa 1, dar nu a cerut rezervarea 1042
COORDINATOR_RADU = 6  # coordonează echipa 2
ADMIN_VLAD = 7  # administrează HPC și sala de seminar
UNKNOWN_ID = 999_999

ANA_BY_START_DESC = [1044, 1042, 1047, 1041, 1040]

MY_RESERVATIONS = "/api/users/me/reservations"


def ids(response: Any) -> list[int]:
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["content"]]


def assert_validation_error(response: Any, field: str) -> None:
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert field in [error["field"] for error in body["errors"]]


# --- GET /users/me/reservations ------------------------------------------------------------


def test_my_reservations_are_ordered_by_start_descending(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    response = client.get(MY_RESERVATIONS)
    assert ids(response) == ANA_BY_START_DESC
    body = response.json()
    assert body["page"] == {"page": 0, "size": 20, "totalElements": 5, "totalPages": 1}
    first = body["content"][0]
    assert first["resource"] == {"id": 7, "name": "Microscop electronic SEM"}
    assert first["project"] == {"id": 2, "title": "Filme subțiri de ZnO"}
    assert first["status"] == "CANCELLED"
    assert set(first) == {"id", "resource", "project", "start", "end", "status"}


def test_my_reservations_contain_only_the_current_users_reservations(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_IOANA)
    assert ids(client.get(MY_RESERVATIONS)) == [1045, 1048, 1043]


def test_my_reservations_filter_by_several_statuses(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    response = client.get(MY_RESERVATIONS, params={"status": ["CANCELLED", "AUTO_CANCELLED"]})
    assert ids(response) == [1044, 1047, 1040]


def test_my_reservations_filter_by_interval_keeps_overlapping_reservations(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    params = {"from": "2026-11-05T10:00:00+02:00", "to": "2026-11-12T11:00:00+02:00"}
    assert ids(client.get(MY_RESERVATIONS, params=params)) == [1042, 1047, 1041]


def test_my_reservations_interval_bounds_are_exclusive(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    # 1041 se termină exact la `from`, iar 1042 începe exact la `to`: niciuna nu se suprapune.
    as_user(STUDENT_ANA)
    params = {"from": "2026-11-05T11:00:00+02:00", "to": "2026-11-12T10:00:00+02:00"}
    assert ids(client.get(MY_RESERVATIONS, params=params)) == [1047]


def test_my_reservations_combine_status_and_interval_filters(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    params = {"status": "CANCELLED", "from": "2026-11-10T00:00:00+02:00"}
    assert ids(client.get(MY_RESERVATIONS, params=params)) == [1044]


def test_my_reservations_are_paginated(client: TestClient, as_user: Callable[[int], None]) -> None:
    as_user(STUDENT_ANA)
    second = client.get(MY_RESERVATIONS, params={"page": 1, "size": 2})
    assert ids(second) == [1047, 1041]
    assert second.json()["page"] == {"page": 1, "size": 2, "totalElements": 5, "totalPages": 3}
    assert ids(client.get(MY_RESERVATIONS, params={"page": 2, "size": 2})) == [1040]
    assert ids(client.get(MY_RESERVATIONS, params={"page": 3, "size": 2})) == []


def test_my_reservations_can_be_sorted_ascending(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    response = client.get(MY_RESERVATIONS, params={"sort": "start,asc"})
    assert ids(response) == list(reversed(ANA_BY_START_DESC))


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"sort": "purpose,asc"}, "sort"),
        ({"status": "WAITING"}, "status.0"),
        ({"size": 101}, "size"),
        ({"page": -1}, "page"),
        ({"from": "ieri"}, "from"),
        ({"from": "2026-11-05T10:00:00"}, "from"),
    ],
)
def test_my_reservations_reject_invalid_parameters(
    client: TestClient, as_user: Callable[[int], None], params: dict[str, Any], field: str
) -> None:
    as_user(STUDENT_ANA)
    assert_validation_error(client.get(MY_RESERVATIONS, params=params), field)


@pytest.mark.parametrize("end", ["2026-11-05T10:00:00+02:00", "2026-11-01T10:00:00+02:00"])
def test_my_reservations_reject_an_interval_that_ends_before_it_starts(
    client: TestClient, as_user: Callable[[int], None], end: str
) -> None:
    as_user(STUDENT_ANA)
    params = {"from": "2026-11-05T10:00:00+02:00", "to": end}
    response = client.get(MY_RESERVATIONS, params=params)
    assert_validation_error(response, "to")
    assert response.json()["errors"][0]["message"] == (
        "Sfârșitul intervalului trebuie să fie după început."
    )


@pytest.mark.parametrize("user_id", [ADMIN_MIHAI, SYSTEM_ADMIN_ELENA])
def test_only_students_and_researchers_have_their_own_reservations(
    client: TestClient, as_user: Callable[[int], None], user_id: int
) -> None:
    as_user(user_id)
    response = client.get(MY_RESERVATIONS)
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"


def test_researchers_see_their_own_reservations(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(COORDINATOR_ANDREI)
    assert ids(client.get(MY_RESERVATIONS)) == [1046]


# --- GET /reservations/{reservationId} -----------------------------------------------------


def test_reservation_details(client: TestClient, as_user: Callable[[int], None]) -> None:
    as_user(STUDENT_ANA)
    response = client.get("/api/reservations/1042")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == 1042
    assert body["resource"] == {"id": 7, "name": "Microscop electronic SEM"}
    assert body["requester"] == {
        "id": STUDENT_ANA,
        "name": "Ana Popescu",
        "email": "ana.popescu@student.usv.ro",
    }
    assert body["project"] == {"id": 1, "title": "Nanostructuri pentru senzori de gaz"}
    assert body["hours"] == 2
    assert body["purpose"] == "Imagini SEM pentru probele de ZnO depuse în octombrie."
    assert body["status"] == "PENDING_ADMIN"
    assert body["approvalFlow"] == "COORDINATOR_AND_ADMIN"
    assert body["checkInDeadline"].startswith("2026-11-12T")
    assert body["checkInAt"] is None
    assert body["checkOutAt"] is None
    assert body["cancellation"] is None
    assert len(body["approvals"]) == 1
    approval = body["approvals"][0]
    assert approval["stage"] == "COORDINATOR"
    assert approval["decision"] == "APPROVED"
    assert approval["approver"]["id"] == COORDINATOR_ANDREI
    assert approval["comment"] is None


def test_reservation_details_show_check_in_and_check_out(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    body = client.get("/api/reservations/1041").json()
    assert body["status"] == "COMPLETED"
    assert body["checkInAt"] is not None
    assert body["checkOutAt"] is not None


def test_reservation_details_list_approvals_in_order(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    approvals = client.get("/api/reservations/1040").json()["approvals"]
    assert [a["stage"] for a in approvals] == ["COORDINATOR", "RESOURCE_ADMIN"]


def test_reservation_details_show_the_rejection_reason(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_IOANA)
    approvals = client.get("/api/reservations/1045").json()["approvals"]
    assert approvals[0]["decision"] == "REJECTED"
    assert approvals[0]["comment"].startswith("Certificarea pentru TEM a fost retrasă")


def test_reservation_details_show_who_cancelled_and_why(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    cancellation = client.get("/api/reservations/1040").json()["cancellation"]
    assert cancellation["cancelledBy"]["id"] == ADMIN_MIHAI
    assert cancellation["reason"] == "Mentenanță: Înlocuirea filamentului."
    assert cancellation["cancelledAt"] is not None


def test_automatic_cancellation_has_no_author(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    body = client.get("/api/reservations/1047").json()
    assert body["status"] == "AUTO_CANCELLED"
    assert body["cancellation"]["cancelledBy"] is None
    assert body["cancellation"]["reason"] == "Fără check-in în termen."


@pytest.mark.parametrize(
    "user_id", [STUDENT_ANA, COORDINATOR_ANDREI, ADMIN_MIHAI, SYSTEM_ADMIN_ELENA]
)
def test_reservation_details_are_visible_to_the_people_involved(
    client: TestClient, as_user: Callable[[int], None], user_id: int
) -> None:
    as_user(user_id)
    assert client.get("/api/reservations/1042").status_code == 200


@pytest.mark.parametrize("user_id", [STUDENT_IOANA, COORDINATOR_RADU, ADMIN_VLAD])
def test_reservation_details_are_hidden_from_everyone_else(
    client: TestClient, as_user: Callable[[int], None], user_id: int
) -> None:
    as_user(user_id)
    response = client.get("/api/reservations/1042")
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"


def test_unknown_reservation_returns_404_before_checking_rights(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_IOANA)
    response = client.get(f"/api/reservations/{UNKNOWN_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Rezervarea {UNKNOWN_ID} nu există."


def test_reservation_id_must_be_positive(client: TestClient) -> None:
    assert_validation_error(client.get("/api/reservations/0"), "reservation_id")
