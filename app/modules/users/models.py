from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(StrEnum):
    """Enumerarea `Rol` din diagrama de clase 8.1."""

    STUDENT = "STUDENT"
    RESEARCHER = "RESEARCHER"
    RESOURCE_ADMIN = "RESOURCE_ADMIN"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class User(Base):
    """Utilizatorul aplicației (tabelul `users`)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('STUDENT', 'RESEARCHER', 'RESOURCE_ADMIN', 'SYSTEM_ADMIN')",
            name="users_role_check",
        ),
        CheckConstraint("NOT two_factor_enabled OR totp_secret IS NOT NULL", name="users_totp_ck"),
        # E-mailul este unic indiferent de majuscule.
        Index("users_email_uq", text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254))
    # Hash Argon2 (pwdlib).
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Text)
    two_factor_enabled: Mapped[bool] = mapped_column(server_default=text("false"))
    # Secretul TOTP (pyotp), criptat de aplicație.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
