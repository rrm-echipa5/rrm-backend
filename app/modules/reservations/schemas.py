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
