from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
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
