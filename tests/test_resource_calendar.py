from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# Datele de test (db/seed.sql) pentru microscopul SEM (resursa 7), în săptămânile 9-22 noiembrie:
# cererea 1042 a Anei (PENDING_ADMIN), rezervarea 1046 a lui Andrei (CONFIRMED) și calibrarea
# programată 31. Rezervările 1040 și 1044 sunt anulate, iar mentenanța 30 e încheiată.
SEM = 7
SEMINAR_ROOM = 11  # nicio rezervare activă
RAMAN = 12
COORDINATOR_ANDREI = 2
STUDENT_ANA = 3
UNKNOWN_ID = 999_999

TWO_WEEKS = {"start": "2026-11-09T00:00:00+02:00", "end": "2026-11-23T00:00:00+02:00"}


def calendar_url(resource_id: int) -> str:
    return f"/api/resources/{resource_id}/calendar"


def moment(value: str) -> datetime:
    return datetime.fromisoformat(value)


def summarize(body: dict[str, Any]) -> list[tuple[datetime, datetime, str, bool, int | None]]:
    return [
        (
            moment(entry["start"]),
            moment(entry["end"]),
            entry["type"],
            entry["own"],
            entry["reservationId"],
        )
        for entry in body["entries"]
    ]


def assert_validation_error(response: Any, field: str) -> None:
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert field in [error["field"] for error in body["errors"]]


def test_calendar_lists_the_busy_intervals_ordered_by_start(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_ANA)
    response = client.get(calendar_url(SEM), params=TWO_WEEKS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resource"] == {"id": SEM, "name": "Microscop electronic SEM"}
    assert moment(body["start"]) == moment(TWO_WEEKS["start"])
    assert moment(body["end"]) == moment(TWO_WEEKS["end"])
    assert body["rules"] == {
        "minDurationMinutes": 30,
        "maxDurationMinutes": 240,
        "breakBetweenMinutes": 15,
        "checkInDeadlineMinutes": 15,
        "requiredCertificationLevel": 2,
    }
    assert summarize(body) == [
        # Cererea proprie care așteaptă administratorul apare ca PENDING, cu id-ul ei.
        (
            moment("2026-11-12T10:00+02:00"),
            moment("2026-11-12T12:00+02:00"),
            "PENDING",
            True,
            1042,
        ),
        # Rezervarea altui utilizator apare fără id.
        (
            moment("2026-11-13T09:00+02:00"),
            moment("2026-11-13T11:00+02:00"),
            "CONFIRMED",
            False,
            None,
        ),
        (
            moment("2026-11-20T08:00+02:00"),
            moment("2026-11-21T18:00+02:00"),
            "MAINTENANCE",
            False,
            None,
        ),
    ]


def test_own_marks_only_the_current_users_reservations(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(COORDINATOR_ANDREI)
    entries = summarize(client.get(calendar_url(SEM), params=TWO_WEEKS).json())

    assert [(kind, own, reservation_id) for _, _, kind, own, reservation_id in entries] == [
        ("PENDING", False, None),
        ("CONFIRMED", True, 1046),
        ("MAINTENANCE", False, None),
    ]


def test_calendar_keeps_only_the_intervals_that_overlap_the_requested_range(
    client: TestClient,
) -> None:
    # Se termină exact când începe cererea 1042 și începe în timpul rezervării 1046.
    params = {"start": "2026-11-12T00:00:00+02:00", "end": "2026-11-13T10:00:00+02:00"}
    entries = summarize(client.get(calendar_url(SEM), params=params).json())
    assert [entry[0] for entry in entries] == [
        moment("2026-11-12T10:00+02:00"),
        moment("2026-11-13T09:00+02:00"),
    ]

    params = {"start": "2026-11-12T00:00:00+02:00", "end": "2026-11-12T10:00:00+02:00"}
    assert client.get(calendar_url(SEM), params=params).json()["entries"] == []

    # Cererea 1042 se termină exact când începe intervalul cerut.
    params = {"start": "2026-11-12T12:00:00+02:00", "end": "2026-11-13T10:00:00+02:00"}
    entries = summarize(client.get(calendar_url(SEM), params=params).json())
    assert [entry[0] for entry in entries] == [moment("2026-11-13T09:00+02:00")]


def test_a_reservation_in_progress_has_its_own_type(
    client: TestClient, db_session: Session
) -> None:
    db_session.execute(text("UPDATE reservations SET status = 'IN_PROGRESS' WHERE id = 1046"))

    entries = summarize(client.get(calendar_url(SEM), params=TWO_WEEKS).json())

    assert [entry[2] for entry in entries] == ["PENDING", "IN_PROGRESS", "MAINTENANCE"]


def test_maintenance_without_end_fills_the_rest_of_the_range(
    client: TestClient, db_session: Session
) -> None:
    db_session.execute(
        text(
            "INSERT INTO maintenance_blocks (resource_id, work_type, start_at, reason, created_by)"
            " VALUES (:resource_id, 'MAINTENANCE', '2026-11-16 08:00+02', 'Defect la laser.', 4)"
        ),
        {"resource_id": RAMAN},
    )

    entries = summarize(client.get(calendar_url(RAMAN), params=TWO_WEEKS).json())

    assert entries[-1] == (
        moment("2026-11-16T08:00+02:00"),
        moment(TWO_WEEKS["end"]),
        "MAINTENANCE",
        False,
        None,
    )


def test_a_free_resource_has_no_entries(client: TestClient) -> None:
    response = client.get(calendar_url(SEMINAR_ROOM), params=TWO_WEEKS)

    assert response.status_code == 200, response.text
    assert response.json()["entries"] == []
    assert response.json()["rules"]["requiredCertificationLevel"] is None


def test_end_must_be_after_start(client: TestClient) -> None:
    params = {"start": TWO_WEEKS["end"], "end": TWO_WEEKS["start"]}
    assert_validation_error(client.get(calendar_url(SEM), params=params), "end")


def test_the_range_has_at_most_31_days(client: TestClient) -> None:
    params = {"start": "2026-11-01T00:00:00+02:00", "end": "2026-12-02T00:00:01+02:00"}
    assert_validation_error(client.get(calendar_url(SEM), params=params), "end")

    params["end"] = "2026-12-02T00:00:00+02:00"
    assert client.get(calendar_url(SEM), params=params).status_code == 200


def test_a_month_with_the_clock_change_fits_in_31_days(client: TestClient) -> None:
    # Octombrie are o oră în plus: 31 de zile pe ceas, 31 de zile și o oră în timp absolut.
    params = {"start": "2026-10-01T00:00:00+03:00", "end": "2026-11-01T00:00:00+02:00"}
    assert client.get(calendar_url(SEM), params=params).status_code == 200


def test_start_and_end_need_a_time_zone(client: TestClient) -> None:
    params = {"start": "2026-11-09T00:00:00", "end": TWO_WEEKS["end"]}
    assert_validation_error(client.get(calendar_url(SEM), params=params), "start")


def test_start_and_end_are_required(client: TestClient) -> None:
    assert_validation_error(
        client.get(calendar_url(SEM), params={"end": TWO_WEEKS["end"]}), "start"
    )


def test_unknown_resource_returns_404(client: TestClient) -> None:
    response = client.get(calendar_url(UNKNOWN_ID), params=TWO_WEEKS)

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "NOT_FOUND"


def test_a_resource_removed_from_the_catalog_returns_404(
    client: TestClient, db_session: Session
) -> None:
    db_session.execute(
        text("UPDATE resources SET deleted_at = now() WHERE id = :id"), {"id": SEMINAR_ROOM}
    )

    response = client.get(calendar_url(SEMINAR_ROOM), params=TWO_WEEKS)

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "NOT_FOUND"


def test_a_resource_without_usage_rules_has_no_rules(
    client: TestClient, db_session: Session
) -> None:
    db_session.execute(
        text("DELETE FROM usage_rules WHERE resource_id = :id"), {"id": SEMINAR_ROOM}
    )

    response = client.get(calendar_url(SEMINAR_ROOM), params=TWO_WEEKS)

    assert response.status_code == 200, response.text
    assert response.json()["rules"] is None
