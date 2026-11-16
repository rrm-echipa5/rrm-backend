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
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.users.models import User


class ResourceCategory(Base):
    """Categoria unei resurse (tabelul `resource_categories`, enumerarea `CategorieResursă`)."""

    __tablename__ = "resource_categories"
    __table_args__ = (
        CheckConstraint(
            "code IN ('HARDWARE', 'HPC', 'ROOM', 'MEASUREMENT_INSTRUMENT')",
            name="resource_categories_code_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Resource(Base):
    """Resursa din catalog (tabelul `resources`); ștergerea este logică, prin `deleted_at`."""

    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'MAINTENANCE', 'FAULTY')", name="resources_status_check"
        ),
        CheckConstraint(
            "approval_flow IN ('AUTO', 'COORDINATOR', 'COORDINATOR_AND_ADMIN')",
            name="resources_approval_flow_check",
        ),
        CheckConstraint(
            "jsonb_typeof(specifications) = 'object'", name="resources_specs_object_ck"
        ),
        Index(
            "resources_category_idx",
            "category_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "resources_admin_idx",
            "administrator_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("resources_tags_gin", "tags", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    category_id: Mapped[int] = mapped_column(ForeignKey("resource_categories.id"))
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict[str, str]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(Text, default="ACTIVE", server_default="ACTIVE")
    approval_flow: Mapped[str] = mapped_column(Text, server_default="COORDINATOR")
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
    __table_args__ = (
        CheckConstraint(
            "min_duration_minutes >= 0", name="usage_rules_min_duration_minutes_check"
        ),
        CheckConstraint(
            "max_duration_minutes >= 1", name="usage_rules_max_duration_minutes_check"
        ),
        CheckConstraint(
            "break_between_minutes >= 0", name="usage_rules_break_between_minutes_check"
        ),
        CheckConstraint(
            "check_in_deadline_minutes BETWEEN 15 AND 30",
            name="usage_rules_check_in_deadline_minutes_check",
        ),
        CheckConstraint(
            "required_certification_level BETWEEN 1 AND 5",
            name="usage_rules_required_certification_level_check",
        ),
        CheckConstraint(
            "min_duration_minutes <= max_duration_minutes", name="usage_rules_duration_ck"
        ),
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    min_duration_minutes: Mapped[int] = mapped_column(
        default=DEFAULT_MIN_DURATION_MINUTES,
        server_default=text(str(DEFAULT_MIN_DURATION_MINUTES)),
    )
    max_duration_minutes: Mapped[int] = mapped_column(
        default=DEFAULT_MAX_DURATION_MINUTES,
        server_default=text(str(DEFAULT_MAX_DURATION_MINUTES)),
    )
    break_between_minutes: Mapped[int] = mapped_column(
        default=DEFAULT_BREAK_BETWEEN_MINUTES,
        server_default=text(str(DEFAULT_BREAK_BETWEEN_MINUTES)),
    )
    check_in_deadline_minutes: Mapped[int] = mapped_column(
        default=DEFAULT_CHECK_IN_DEADLINE_MINUTES,
        server_default=text(str(DEFAULT_CHECK_IN_DEADLINE_MINUTES)),
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
