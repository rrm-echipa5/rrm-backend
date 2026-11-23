from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.maintenance.models import MaintenanceBlock
from app.modules.projects.models import Project
from app.modules.resources.models import Resource
from app.modules.users.models import User


class ReservationStatus(StrEnum):
    """Enumerarea `StareRezervare` (diagrama de stări 7.1)."""

    PENDING = "PENDING"
    PENDING_ADMIN = "PENDING_ADMIN"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    AUTO_CANCELLED = "AUTO_CANCELLED"


class Approval(Base):
    """O decizie de aprobare sau respingere (tabelul `approvals`, câte una pe etapă)."""

    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('COORDINATOR', 'RESOURCE_ADMIN')", name="approvals_stage_check"
        ),
        CheckConstraint("decision IN ('APPROVED', 'REJECTED')", name="approvals_decision_check"),
        UniqueConstraint("reservation_id", "stage", name="approvals_reservation_id_stage_key"),
        # Respingerea are întotdeauna un motiv.
        CheckConstraint(
            "decision = 'APPROVED' OR comment IS NOT NULL", name="approvals_reject_reason_ck"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    comment: Mapped[str | None] = mapped_column(String(500))

    approver: Mapped[User] = relationship(lazy="joined")


class Reservation(Base):
    """Cererea de rezervare sau rezervarea (tabelul `reservations`)."""

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS',"
            " 'COMPLETED', 'REJECTED', 'CANCELLED', 'AUTO_CANCELLED')",
            name="reservations_status_check",
        ),
        CheckConstraint(
            "approval_flow IN ('AUTO', 'COORDINATOR', 'COORDINATOR_AND_ADMIN')",
            name="reservations_approval_flow_check",
        ),
        CheckConstraint(
            "check_in_method IN ('WEB', 'QR')", name="reservations_check_in_method_check"
        ),
        CheckConstraint("end_at > start_at", name="reservations_interval_ck"),
        CheckConstraint(
            "check_in_deadline > start_at AND check_in_deadline <= end_at",
            name="reservations_deadline_ck",
        ),
        CheckConstraint(
            "(check_in_at IS NULL) = (check_in_method IS NULL)", name="reservations_check_in_ck"
        ),
        CheckConstraint(
            "(status IN ('CANCELLED', 'AUTO_CANCELLED')) = (cancelled_at IS NOT NULL)",
            name="reservations_cancel_ck",
        ),
        # Intervalul unei cereri active blochează resursa: nicio altă cerere activă nu se poate
        # suprapune (409 SLOT_UNAVAILABLE). Pauza dintre rezervări se verifică în serviciu.
        ExcludeConstraint(
            ("resource_id", "="),
            (text("tstzrange(start_at, end_at, '[)')"), "&&"),
            name="reservations_no_overlap",
            using="gist",
            where=text("status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS')"),
        ),
        Index("reservations_project_idx", "project_id"),
        Index("reservations_resource_time_idx", "resource_id", "start_at"),
        Index(
            "reservations_pending_idx",
            "status",
            postgresql_where=text("status IN ('PENDING', 'PENDING_ADMIN')"),
        ),
        Index(
            "reservations_check_in_due_idx",
            "check_in_deadline",
            postgresql_where=text("status = 'CONFIRMED'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Coloană calculată de PostgreSQL din interval; nu se scrie din aplicație.
    hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        Computed(
            "round((extract(epoch FROM (end_at - start_at)) / 3600)::numeric, 2)",
            persisted=True,
        ),
        # Ca în `db/schema.sql`, coloana nu are NOT NULL; valoarea există mereu, pentru că
        # `start_at` și `end_at` sunt obligatorii.
        nullable=True,
    )
    purpose: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(Text)
    # Fluxul de aprobare al resursei la momentul cererii.
    approval_flow: Mapped[str] = mapped_column(Text)
    # `start_at` plus termenul de check-in din regulile resursei.
    check_in_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_method: Mapped[str | None] = mapped_column(Text)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[int | None] = mapped_column("cancelled_by", ForeignKey("users.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    # Blocarea de mentenanță care a anulat rezervarea.
    maintenance_id: Mapped[int | None] = mapped_column(ForeignKey(MaintenanceBlock.id))

    resource: Mapped[Resource] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requester_id], lazy="joined")
    project: Mapped[Project] = relationship(lazy="joined")
    cancelled_by: Mapped[User | None] = relationship(foreign_keys=[cancelled_by_id], lazy="joined")
    approvals: Mapped[list[Approval]] = relationship(
        order_by=(Approval.decided_at, Approval.id), lazy="selectin"
    )


Index("reservations_requester_idx", Reservation.requester_id, Reservation.start_at.desc())
