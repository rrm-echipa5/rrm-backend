from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# Utilizatorii din datele de test (db/seed.sql).
SYSTEM_ADMIN_ELENA = 1
COORDINATOR_ANDREI = 2  # coordonează echipa 1 (proiectele 1 și 2)
STUDENT_ANA = 3
ADMIN_MIHAI = 4  # administrează SEM și Raman
STUDENT_IOANA = 5  # membră în echipele 1 și 2
COORDINATOR_RADU = 6  # coordonează echipa 2 (proiectul 3)
RAMAN_ID = 12
HPC_ID = 10  # flux AUTO, administrat de Vlad Popa
PROJECT_NANO = 1  # echipa 1
UNKNOWN_ID = 999_999

# Rezervări noi, în viitor, ca să nu depindă de data la care rulează testele.
INSERT_RESERVATION = text(
    """
    INSERT INTO reservations (resource_id, requester_id, project_id, start_at, end_at, purpose,
                              status, approval_flow, check_in_deadline, check_in_at,
                              check_in_method, check_out_at, cancelled_at)
    VALUES (:resource_id, :requester_id, :project_id,
            '2027-03-01 10:00+02'::timestamptz + make_interval(days => :day),
            '2027-03-01 13:00+02'::timestamptz + make_interval(days => :day),
            'Test de anulare', :status, :approval_flow,
            '2027-03-01 10:15+02'::timestamptz + make_interval(days => :day),
            CASE WHEN :status IN ('IN_PROGRESS', 'COMPLETED')
                 THEN '2027-03-01 10:05+02'::timestamptz + make_interval(days => :day) END,
            CASE WHEN :status IN ('IN_PROGRESS', 'COMPLETED') THEN 'WEB' END,
            CASE WHEN :status = 'COMPLETED'
                 THEN '2027-03-01 12:55+02'::timestamptz + make_interval(days => :day) END,
            CASE WHEN :status IN ('CANCELLED', 'AUTO_CANCELLED') THEN now() END)
    RETURNING id
    """
)
INSERT_APPROVAL = text(
    """
    INSERT INTO approvals (reservation_id, stage, decision, approver_id)
    VALUES (:reservation_id, :stage, 'APPROVED', :approver_id)
    """
)


def add_reservation(  # noqa: PLR0913 - câmpurile rezervării de test
    db_session: Session,
    status: str,
    *,
    resource_id: int = RAMAN_ID,
    requester_id: int = STUDENT_ANA,
    project_id: int = PROJECT_NANO,
    approval_flow: str = "COORDINATOR",
    day: int = 0,
) -> int:
    reservation_id = db_session.scalar(
        INSERT_RESERVATION,
        {
            "resource_id": resource_id,
            "requester_id": requester_id,
            "project_id": project_id,
            "status": status,
            "approval_flow": approval_flow,
            "day": day,
        },
    )
    assert reservation_id is not None
    return int(reservation_id)


def used_hours(db_session: Session, project_id: int) -> float:
    query = text("SELECT used_hours FROM project_budgets WHERE id = :id")
    return float(db_session.scalar(query, {"id": project_id}))


def notified(db_session: Session, reservation_id: int) -> list[int]:
    query = text(
        """
        SELECT recipient_id FROM notifications
        WHERE reservation_id = :id AND type = 'RESERVATION_CANCELLED' ORDER BY recipient_id
        """
    )
    return list(db_session.scalars(query, {"id": reservation_id}))


def status_of(db_session: Session, reservation_id: int) -> str:
    query = text("SELECT status FROM reservations WHERE id = :id")
    return str(db_session.scalar(query, {"id": reservation_id}))


def cancel(client: TestClient, reservation_id: int, **body: Any) -> Any:
    url = f"/api/reservations/{reservation_id}/cancel"
    return client.post(url, json=body) if body else client.post(url)


# --- Stări -------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["PENDING", "PENDING_ADMIN", "CONFIRMED"])
def test_requester_can_cancel_from_every_allowed_state(
    client: TestClient, db_session: Session, as_user: Callable[[int], None], status: str
) -> None:
    reservation_id = add_reservation(db_session, status)
    as_user(STUDENT_ANA)
    response = cancel(client, reservation_id, reason="Proba nu este gata.")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancellation"]["cancelledBy"]["id"] == STUDENT_ANA
    assert body["cancellation"]["reason"] == "Proba nu este gata."
    assert body["cancellation"]["cancelledAt"] is not None
    assert status_of(db_session, reservation_id) == "CANCELLED"


@pytest.mark.parametrize(
    "status", ["IN_PROGRESS", "COMPLETED", "REJECTED", "CANCELLED", "AUTO_CANCELLED"]
)
def test_cancel_is_refused_from_the_other_states(
    client: TestClient, db_session: Session, as_user: Callable[[int], None], status: str
) -> None:
    reservation_id = add_reservation(db_session, status)
    as_user(STUDENT_ANA)
    response = cancel(client, reservation_id)
    assert response.status_code == 409
    problem = response.json()
    assert problem["code"] == "INVALID_STATE"
    assert problem["detail"] == f"Rezervarea are statusul {status} și nu mai poate fi anulată."
    assert status_of(db_session, reservation_id) == status
    assert notified(db_session, reservation_id) == []


def test_cancelled_reservation_cannot_be_cancelled_twice(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "PENDING")
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id).status_code == 200
    assert cancel(client, reservation_id).status_code == 409


# --- Bugetul și intervalul ------------------------------------------------------------------


def test_cancelling_a_confirmed_reservation_returns_its_hours_to_the_project(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    before = used_hours(db_session, PROJECT_NANO)
    reservation_id = add_reservation(db_session, "CONFIRMED")
    assert used_hours(db_session, PROJECT_NANO) == before + 3
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id).status_code == 200
    assert used_hours(db_session, PROJECT_NANO) == before


def test_cancelling_frees_the_interval(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "CONFIRMED")
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id).status_code == 200
    # Fără anulare, constrângerea `reservations_no_overlap` ar refuza aceeași perioadă.
    add_reservation(db_session, "PENDING", requester_id=STUDENT_IOANA)


# --- Drepturi ------------------------------------------------------------------------------


def test_team_coordinator_can_cancel_a_members_reservation(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "CONFIRMED")
    as_user(COORDINATOR_ANDREI)
    response = cancel(client, reservation_id)
    assert response.status_code == 200, response.text
    assert response.json()["cancellation"]["cancelledBy"]["id"] == COORDINATOR_ANDREI


@pytest.mark.parametrize(
    "user_id", [STUDENT_IOANA, COORDINATOR_RADU, ADMIN_MIHAI, SYSTEM_ADMIN_ELENA]
)
def test_only_the_requester_and_the_coordinator_can_cancel(
    client: TestClient, db_session: Session, as_user: Callable[[int], None], user_id: int
) -> None:
    reservation_id = add_reservation(db_session, "PENDING")
    as_user(user_id)
    response = cancel(client, reservation_id)
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"
    assert status_of(db_session, reservation_id) == "PENDING"


def test_cancel_unknown_reservation_returns_404_before_checking_rights(
    client: TestClient, as_user: Callable[[int], None]
) -> None:
    as_user(STUDENT_IOANA)
    response = cancel(client, UNKNOWN_ID)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# --- Motivul ---------------------------------------------------------------------------------


@pytest.mark.parametrize("body", [{}, {"reason": None}, {"reason": "   "}])
def test_reason_is_optional(
    client: TestClient,
    db_session: Session,
    as_user: Callable[[int], None],
    body: dict[str, Any],
) -> None:
    reservation_id = add_reservation(db_session, "PENDING")
    as_user(STUDENT_ANA)
    response = cancel(client, reservation_id, **body)
    assert response.status_code == 200, response.text
    assert response.json()["cancellation"]["reason"] is None


def test_reason_is_limited_to_500_characters(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "PENDING")
    as_user(STUDENT_ANA)
    response = cancel(client, reservation_id, reason="x" * 501)
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "reason"
    assert status_of(db_session, reservation_id) == "PENDING"


# --- Notificări ---------------------------------------------------------------------------


def test_pending_cancel_notifies_the_coordinator(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "PENDING")
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id, reason="Proba nu este gata.").status_code == 200
    assert notified(db_session, reservation_id) == [COORDINATOR_ANDREI]
    title, body, channel = db_session.execute(
        text("SELECT title, body, channel FROM notifications WHERE reservation_id = :id"),
        {"id": reservation_id},
    ).one()
    assert title == "Rezervare anulată: Spectrometru Raman"
    assert body == (
        "Rezervarea pentru Spectrometru Raman din 01.03.2027, 10:00-13:00 "
        "(solicitant: Ana Popescu) a fost anulată de Ana Popescu. Motiv: Proba nu este gata."
    )
    assert channel == "IN_APP"


def test_pending_admin_cancel_notifies_the_coordinator_and_the_resource_admin(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "PENDING_ADMIN")
    db_session.execute(
        INSERT_APPROVAL,
        {"reservation_id": reservation_id, "stage": "COORDINATOR", "approver_id": 2},
    )
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id).status_code == 200
    assert notified(db_session, reservation_id) == [COORDINATOR_ANDREI, ADMIN_MIHAI]


def test_confirmed_cancel_notifies_the_approvers_who_decided(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "CONFIRMED")
    for stage, approver_id in [("COORDINATOR", 2), ("RESOURCE_ADMIN", 4)]:
        db_session.execute(
            INSERT_APPROVAL,
            {"reservation_id": reservation_id, "stage": stage, "approver_id": approver_id},
        )
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id).status_code == 200
    assert notified(db_session, reservation_id) == [COORDINATOR_ANDREI, ADMIN_MIHAI]


def test_auto_approved_cancel_notifies_nobody(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(
        db_session, "CONFIRMED", resource_id=HPC_ID, approval_flow="AUTO"
    )
    as_user(STUDENT_ANA)
    assert cancel(client, reservation_id).status_code == 200
    assert notified(db_session, reservation_id) == []


def test_the_canceller_is_not_notified(
    client: TestClient, db_session: Session, as_user: Callable[[int], None]
) -> None:
    reservation_id = add_reservation(db_session, "PENDING")
    as_user(COORDINATOR_ANDREI)
    assert cancel(client, reservation_id).status_code == 200
    assert notified(db_session, reservation_id) == []
