from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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


class Certification(Base):
    """Certificarea unui utilizator pentru o resursă (tabelul `certifications`).

    Starea din API nu se păstrează: o calculează vederea `certification_statuses`
    (REVOKED dacă `revoked_at` e completat, EXPIRED dacă `expires_at` a trecut, altfel ACTIVE).
    """

    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 5", name="certifications_level_check"),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoke_reason IS NULL)"
            " AND (revoked_at IS NULL) = (revoked_by IS NULL)",
            name="certifications_revoke_ck",
        ),
        # Cel mult o certificare nerevocată per (utilizator, resursă): 409 CERTIFICATION_EXISTS.
        Index(
            "certifications_one_open_uq",
            "user_id",
            "resource_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("certifications_resource_idx", "resource_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    resource_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resources.id", ondelete="CASCADE")
    )
    level: Mapped[int] = mapped_column(SmallInteger)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    granted_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    expires_at: Mapped[date | None] = mapped_column(Date)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
