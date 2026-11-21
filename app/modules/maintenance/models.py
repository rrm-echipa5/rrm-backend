from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaintenanceBlock(Base):
    """Blocarea unei resurse pentru mentenanță sau calibrare (tabelul `maintenance_blocks`).

    `end_at` gol înseamnă o blocare pe durată nedeterminată.
    """

    __tablename__ = "maintenance_blocks"
    __table_args__ = (
        CheckConstraint(
            "work_type IN ('MAINTENANCE', 'CALIBRATION')",
            name="maintenance_blocks_work_type_check",
        ),
        CheckConstraint(
            "status IN ('SCHEDULED', 'ACTIVE', 'ENDED', 'CANCELLED')",
            name="maintenance_blocks_status_check",
        ),
        CheckConstraint("end_at IS NULL OR end_at > start_at", name="maintenance_interval_ck"),
        CheckConstraint(
            "(status = 'ENDED') = (ended_at IS NOT NULL)"
            " AND (status = 'CANCELLED') = (cancelled_at IS NOT NULL)",
            name="maintenance_status_dates_ck",
        ),
        # Două blocări programate sau în curs nu se pot suprapune pe aceeași resursă
        # (409 MAINTENANCE_OVERLAP).
        ExcludeConstraint(
            ("resource_id", "="),
            (text("tstzrange(start_at, end_at, '[)')"), "&&"),
            name="maintenance_no_overlap",
            using="gist",
            where=text("status IN ('SCHEDULED', 'ACTIVE')"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resources.id", ondelete="CASCADE")
    )
    work_type: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(Text, server_default="SCHEDULED")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "maintenance_blocks_resource_idx",
    MaintenanceBlock.resource_id,
    MaintenanceBlock.start_at.desc(),
)
