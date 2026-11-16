from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    """Echipa de cercetare (tabelul `teams`), doar câmpurile folosite până acum."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    coordinator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Project(Base):
    """Proiectul unei echipe (tabelul `projects`), pe bugetul căruia se fac rezervările."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(String(200))

    team: Mapped[Team] = relationship(lazy="joined")
