from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    """Echipa de cercetare (tabelul `teams`)."""

    __tablename__ = "teams"
    __table_args__ = (Index("teams_coordinator_idx", "coordinator_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    coordinator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    """Proiectul unei echipe (tabelul `projects`), pe bugetul căruia se fac rezervările.

    Orele consumate nu se păstrează aici: le calculează vederea `project_budgets`.
    """

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("budget_hours >= 0", name="projects_budget_hours_check"),
        UniqueConstraint("team_id", "title", name="projects_team_id_title_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    budget_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    team: Mapped[Team] = relationship(lazy="joined")
