from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.maintenance.models import MaintenanceBlock


class NotificationChannel(StrEnum):
    """Canalul pe care se trimite notificarea."""

    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class NotificationType(StrEnum):
    """Tipurile de notificări folosite până acum (`NotificationType` din rrm-api.yaml)."""

    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"


class Notification(Base):
    """O notificare pentru un utilizator (tabelul `notifications`)."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('EMAIL', 'IN_APP')", name="notifications_channel_check"),
        # E-mailurile încă netrimise, în ordinea în care au fost create.
        Index(
            "notifications_outbox_idx",
            "created_at",
            postgresql_where=text("channel = 'EMAIL' AND sent_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="SET NULL")
    )
    maintenance_id: Mapped[int | None] = mapped_column(
        ForeignKey(MaintenanceBlock.id, ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Doar pentru IN_APP.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Doar pentru EMAIL; gol înseamnă că e-mailul încă nu a fost trimis.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(String(500))


# Inboxul unui utilizator: notificările din aplicație, cele mai noi primele.
Index(
    "notifications_inbox_idx",
    Notification.recipient_id,
    Notification.created_at.desc(),
    postgresql_where=text("channel = 'IN_APP'"),
)
