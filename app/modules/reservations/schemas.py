"""Schemele JSON ale rezervărilor, cu aceleași nume ca în `rrm-api.yaml`."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints

from app.modules.reservations.models import ReservationStatus
from app.modules.resources.schemas import ApiModel, ApprovalFlow, PageMeta, UserRef


class ApprovalStage(StrEnum):
    """Etapa aprobării."""

    COORDINATOR = "COORDINATOR"
    RESOURCE_ADMIN = "RESOURCE_ADMIN"


class Decision(StrEnum):
    """Decizia unei aprobări."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ResourceRef(ApiModel):
    """Referința la o resursă (`ResourceRef`)."""

    id: int
    name: str


class ProjectRef(ApiModel):
    """Referința la un proiect (`ProjectRef`)."""

    id: int
    title: str


class ApprovalOut(ApiModel):
    """O decizie de aprobare sau respingere (`Approval`)."""

    id: int
    stage: ApprovalStage
    decision: Decision
    approver: UserRef
    decided_at: datetime
    comment: str | None


class Cancellation(ApiModel):
    """Anularea unei rezervări (`Cancellation`).

    `cancelledBy` lipsește la anularea automată (fără check-in), iar `reason` este `null`
    dacă solicitantul nu a dat un motiv.
    """

    cancelled_at: datetime
    cancelled_by: UserRef | None
    reason: str | None


class ReservationSummary(ApiModel):
    """Rezervarea, așa cum apare în lista „Rezervările mele” (`ReservationSummary`)."""

    id: int
    resource: ResourceRef
    project: ProjectRef
    start: datetime = Field(validation_alias="start_at")
    end: datetime = Field(validation_alias="end_at")
    status: ReservationStatus


class ReservationSummaryPage(ApiModel):
    """O pagină de rezervări (`ReservationSummaryPage`)."""

    content: list[ReservationSummary]
    page: PageMeta


class CancelReservationRequest(ApiModel):
    """Corpul opțional al anulării (`CancelReservationRequest`)."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class ReservationOut(ReservationSummary):
    """Detaliile unei rezervări (`Reservation`), cu istoricul aprobărilor."""

    requester: UserRef
    hours: float
    purpose: str
    approval_flow: ApprovalFlow
    check_in_deadline: datetime
    check_in_at: datetime | None
    check_out_at: datetime | None
    created_at: datetime
    cancellation: Cancellation | None = None
    approvals: list[ApprovalOut]


class CalendarEntryType(StrEnum):
    """Ce ocupă un interval din calendar; `PENDING` include și `PENDING_ADMIN`."""

    CONFIRMED = "CONFIRMED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    MAINTENANCE = "MAINTENANCE"


class CalendarEntry(ApiModel):
    """Un interval ocupat din calendarul resursei (`CalendarEntry`)."""

    start: datetime
    end: datetime
    type: CalendarEntryType
    # Dacă intervalul este o rezervare a utilizatorului curent.
    own: bool
    # Doar pentru rezervările proprii; `None` pentru ale altora și pentru mentenanță.
    reservation_id: int | None = None


class UsageRuleSummary(ApiModel):
    """Regulile de utilizare de care ține cont calendarul (`UsageRuleSummary`)."""

    min_duration_minutes: int
    max_duration_minutes: int
    break_between_minutes: int
    check_in_deadline_minutes: int
    required_certification_level: int | None


class ResourceCalendar(ApiModel):
    """Calendarul disponibilității unei resurse (`ResourceCalendar`)."""

    resource: ResourceRef
    start: datetime
    end: datetime
    rules: UsageRuleSummary
    # Intervalele ocupate, ordonate după început; restul intervalului este liber.
    entries: list[CalendarEntry]
