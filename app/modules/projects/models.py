from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    """Echipa de cercetare (tabelul `teams`), doar câmpurile folosite până acum."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    coordinator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TeamMember(Base):
    """Apartenența unui utilizator la o echipă (tabelul `team_members`, asocierea M:N)."""

    __tablename__ = "team_members"
    __table_args__ = (Index("team_members_user_idx", "user_id"),)

    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    """Proiectul unei echipe (tabelul `projects`), pe bugetul căruia se fac rezervările."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(String(200))

    team: Mapped[Team] = relationship(lazy="joined")
