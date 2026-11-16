from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str]
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
