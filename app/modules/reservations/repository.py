from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.maintenance.models import MaintenanceBlock
from app.modules.notifications.models import Notification
from app.modules.reservations.models import Reservation, ReservationStatus
from app.modules.resources.models import Resource
from app.modules.users.models import User

# Rezervările care ocupă resursa în calendar: cererile în așteptare, rezervările confirmate și
# cele în desfășurare (aceleași stări ca în constrângerea `reservations_no_overlap`).
BLOCKING_RESERVATION_STATUSES = (
    ReservationStatus.PENDING,
    ReservationStatus.PENDING_ADMIN,
    ReservationStatus.CONFIRMED,
    ReservationStatus.IN_PROGRESS,
)
# Blocările de mentenanță care ocupă resursa (programate sau în curs).
BLOCKING_MAINTENANCE_STATUSES = ("SCHEDULED", "ACTIVE")

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

    def find_resource(self, resource_id: int) -> Resource | None:
        """Întoarce resursa din catalog (nestearsă) cu id-ul dat, cu regulile ei, sau `None`."""
        statement = select(Resource).where(
            Resource.id == resource_id, Resource.deleted_at.is_(None)
        )
        return self._session.scalars(statement).first()

    def find_blocking_reservations(
        self, resource_id: int, start: datetime, end: datetime
    ) -> Sequence[Reservation]:
        """Întoarce rezervările care ocupă resursa și se suprapun cu intervalul `[start, end)`."""
        statement = select(Reservation).where(
            Reservation.resource_id == resource_id,
            Reservation.status.in_(BLOCKING_RESERVATION_STATUSES),
            Reservation.start_at < end,
            Reservation.end_at > start,
        )
        return self._session.scalars(statement).all()

    def find_blocking_maintenance(
        self, resource_id: int, start: datetime, end: datetime
    ) -> Sequence[MaintenanceBlock]:
        """Întoarce blocările de mentenanță care se suprapun cu intervalul `[start, end)`.

        O blocare fără sfârșit (durată nedeterminată) ține până la anulare sau încheiere.
        """
        statement = select(MaintenanceBlock).where(
            MaintenanceBlock.resource_id == resource_id,
            MaintenanceBlock.status.in_(BLOCKING_MAINTENANCE_STATUSES),
            MaintenanceBlock.start_at < end,
            or_(MaintenanceBlock.end_at.is_(None), MaintenanceBlock.end_at > start),
        )
        return self._session.scalars(statement).all()

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
