import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TwoFactorChallenge(Base):
    """Pasul 2 al autentificării (tabelul `two_factor_challenges`), valabil 5 minute.

    `id` este `challengeId` primit la `POST /auth/login`.
    """

    __tablename__ = "two_factor_challenges"
    __table_args__ = (
        CheckConstraint("attempts BETWEEN 0 AND 5", name="two_factor_challenges_attempts_check"),
        Index("two_factor_challenges_user_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TrustedDevice(Base):
    """Dispozitiv memorat 5 zile după autentificare (tabelul `trusted_devices`)."""

    __tablename__ = "trusted_devices"
    __table_args__ = (Index("trusted_devices_user_idx", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RefreshToken(Base):
    """Token de reînnoire a sesiunii (tabelul `refresh_tokens`).

    Folosit de `POST /auth/refresh` și retras la `POST /auth/logout`.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("refresh_tokens_user_idx", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
