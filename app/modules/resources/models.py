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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.users.models import User


class ResourceCategory(Base):
    """Categoria unei resurse (tabelul `resource_categories`, enumerarea `CategorieResursă`)."""

    __tablename__ = "resource_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str]
    name: Mapped[str] = mapped_column(String(100))


class Resource(Base):
    """Resursa din catalog (tabelul `resources`); ștergerea este logică, prin `deleted_at`."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    category_id: Mapped[int] = mapped_column(ForeignKey("resource_categories.id"))
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[str] = mapped_column(default="ACTIVE")
    approval_flow: Mapped[str]
    administrator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    check_in_qr_code: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped[ResourceCategory] = relationship(lazy="joined")
    administrator: Mapped[User] = relationship(lazy="joined")
    usage_rule: Mapped["UsageRule | None"] = relationship(
        back_populates="resource", lazy="joined", cascade="all, delete-orphan"
    )

    @property
    def required_certification_level(self) -> int | None:
        """Nivelul de certificare cerut de reguli, afișat și în catalog."""
        return self.usage_rule.required_certification_level if self.usage_rule else None


# Regulile implicite ale unei resurse noi (`POST /resources` din rrm-api.yaml), aceleași ca
# valorile implicite ale coloanelor din `usage_rules`.
DEFAULT_MIN_DURATION_MINUTES = 30
DEFAULT_MAX_DURATION_MINUTES = 240
DEFAULT_BREAK_BETWEEN_MINUTES = 0
DEFAULT_CHECK_IN_DEADLINE_MINUTES = 15


class UsageRule(Base):
    """Regulile de utilizare ale resursei (tabelul `usage_rules`, 1:1 cu resursa).

    Fluxul de aprobare stă în tabelul `resources`, dar în API face parte din `UsageRule`.
    """

    __tablename__ = "usage_rules"

    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    min_duration_minutes: Mapped[int] = mapped_column(default=DEFAULT_MIN_DURATION_MINUTES)
    max_duration_minutes: Mapped[int] = mapped_column(default=DEFAULT_MAX_DURATION_MINUTES)
    break_between_minutes: Mapped[int] = mapped_column(default=DEFAULT_BREAK_BETWEEN_MINUTES)
    check_in_deadline_minutes: Mapped[int] = mapped_column(
        default=DEFAULT_CHECK_IN_DEADLINE_MINUTES
    )
    required_certification_level: Mapped[int | None] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by_id: Mapped[int | None] = mapped_column("updated_by", ForeignKey("users.id"))

    resource: Mapped[Resource] = relationship(back_populates="usage_rule")
    updated_by: Mapped[User | None] = relationship(lazy="joined")

    @property
    def approval_flow(self) -> str:
        """Fluxul de aprobare al resursei, afișat împreună cu regulile."""
        return self.resource.approval_flow


class ResourceFile(Base):
    """Manualul PDF sau poza unei resurse (tabelul `resource_files`).

    Conținutul stă în stocarea de fișiere; tabelul păstrează doar metadatele.
    """

    __tablename__ = "resource_files"
    __table_args__ = (
        CheckConstraint("type IN ('MANUAL', 'PHOTO')", name="resource_files_type_check"),
        # Cel mult 20 MB.
        CheckConstraint(
            "size_bytes BETWEEN 0 AND 20971520", name="resource_files_size_bytes_check"
        ),
        Index("resource_files_resource_idx", "resource_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resources.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
