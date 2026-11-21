from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification
from app.modules.reservations.models import Reservation
from app.modules.users.models import User

# Câmpurile după care se poate sorta lista „Rezervările mele” (`sort=câmp,asc|desc`).
SORTABLE_COLUMNS = {
    "id": Reservation.id,
    "start": Reservation.start_at,
    "end": Reservation.end_at,
    "status": Reservation.status,
    "createdAt": Reservation.created_at,
}


@dataclass(frozen=True)
class ReservationFilter:
    """Filtrele și sortarea rezervărilor unui utilizator.

    `starts_before` păstrează rezervările care încep înainte de acel moment (parametrul `to`),
    iar `ends_after` pe cele care se termină după el (parametrul `from`), deci rămân toate
    rezervările care se suprapun cu intervalul cerut.
    """

    requester_id: int
    statuses: tuple[str, ...] = ()
    ends_after: datetime | None = None
    starts_before: datetime | None = None
    sort_field: str = "start"
    descending: bool = True


class ReservationRepository:
    """Citește și scrie rezervările în PostgreSQL.

    Args:
        session: Sesiunea SQLAlchemy a cererii curente.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_user(self, user_id: int) -> User | None:
        """Întoarce utilizatorul cu id-ul dat sau `None`."""
        return self._session.get(User, user_id)

    def find_by_id(self, reservation_id: int) -> Reservation | None:
        """Întoarce rezervarea cu id-ul dat, cu resursa, proiectul și aprobările, sau `None`."""
        return self._session.get(Reservation, reservation_id)

    def find_by_id_for_update(self, reservation_id: int) -> Reservation | None:
        """Ca `find_by_id`, dar blochează rândul până la commit.

        Astfel, o anulare și o aprobare trimise în același timp nu pot schimba amândouă
        statusul pornind de la aceeași stare.
        """
        statement = (
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update(of=Reservation)
            .execution_options(populate_existing=True)
        )
        return self._session.scalars(statement).first()

    def add_notifications(self, notifications: Sequence[Notification]) -> None:
        """Adaugă notificările; se salvează la următorul commit."""
        self._session.add_all(notifications)

    def commit_and_refresh(self, reservation: Reservation) -> None:
        """Salvează modificările și reîncarcă rezervarea."""
        self._session.commit()
        self._session.refresh(reservation)

    def find_page(
        self, reservation_filter: ReservationFilter, page: int, size: int
    ) -> tuple[Sequence[Reservation], int]:
        """Întoarce o pagină de rezervări și numărul total al celor care trec de filtre."""
        statement = self._filtered(reservation_filter)
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        column = SORTABLE_COLUMNS[reservation_filter.sort_field]
        if reservation_filter.descending:
            order = (column.desc(), Reservation.id.desc())
        else:
            order = (column.asc(), Reservation.id.asc())
        items = self._session.scalars(
            statement.order_by(*order).offset(page * size).limit(size)
        ).all()
        return items, total

    @staticmethod
    def _filtered(reservation_filter: ReservationFilter) -> Select[Reservation]:
        statement = select(Reservation).where(
            Reservation.requester_id == reservation_filter.requester_id
        )
        if reservation_filter.statuses:
            statement = statement.where(Reservation.status.in_(reservation_filter.statuses))
        if reservation_filter.ends_after is not None:
            statement = statement.where(Reservation.end_at > reservation_filter.ends_after)
        if reservation_filter.starts_before is not None:
            statement = statement.where(Reservation.start_at < reservation_filter.starts_before)
        return statement
