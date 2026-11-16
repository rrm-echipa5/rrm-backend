from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Computed, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"))
    stage: Mapped[str]
    decision: Mapped[str]
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(String(500))

    approver: Mapped[User] = relationship(lazy="joined")


class Reservation(Base):
    """Cererea de rezervare sau rezervarea (tabelul `reservations`)."""

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Coloană calculată de PostgreSQL din interval; nu se scrie din aplicație.
    hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        Computed("round((extract(epoch FROM (end_at - start_at)) / 3600)::numeric, 2)"),
    )
    purpose: Mapped[str] = mapped_column(String(500))
    status: Mapped[str]
    approval_flow: Mapped[str]
    check_in_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[int | None] = mapped_column("cancelled_by", ForeignKey("users.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))

    resource: Mapped[Resource] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requester_id], lazy="joined")
    project: Mapped[Project] = relationship(lazy="joined")
    cancelled_by: Mapped[User | None] = relationship(foreign_keys=[cancelled_by_id], lazy="joined")
    approvals: Mapped[list[Approval]] = relationship(
        order_by=(Approval.decided_at, Approval.id), lazy="selectin"
    )
