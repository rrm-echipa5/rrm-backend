from enum import StrEnum

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(StrEnum):
    """Enumerarea `Rol` din diagrama de clase 8.1."""

    STUDENT = "STUDENT"
    RESEARCHER = "RESEARCHER"
    RESOURCE_ADMIN = "RESOURCE_ADMIN"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class User(Base):
    """Utilizatorul aplicației (tabelul `users`), doar câmpurile folosite până acum."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str]
