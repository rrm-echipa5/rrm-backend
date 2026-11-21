import math
from datetime import datetime

from app.core.errors import ForbiddenError, NotFoundError
from app.modules.reservations.models import Reservation, ReservationStatus
from app.modules.reservations.repository import ReservationFilter, ReservationRepository
from app.modules.reservations.schemas import (
    CalendarEntry,
    CalendarEntryType,
    Cancellation,
    ReservationOut,
    ReservationSummary,
    ReservationSummaryPage,
    ResourceCalendar,
    ResourceRef,
    UsageRuleSummary,
)
from app.modules.resources.schemas import PageMeta, UserRef
from app.modules.users.models import Role

# Rolurile care au rezervări proprii (`GET /users/me/reservations` din rrm-api.yaml).
REQUESTER_ROLES = frozenset({Role.STUDENT, Role.RESEARCHER})


class ReservationService:
    """Regulile de business pentru rezervările unui utilizator (KAN-77).

    Până la autentificare (KAN-64), utilizatorul curent este cel din setarea
    `RRM_DEMO_USER_ID`. Drepturile urmează `rrm-api.yaml`: lista proprie o văd `STUDENT` și
    `RESEARCHER`, iar detaliile unei rezervări solicitantul, coordonatorul echipei
    proiectului, administratorul resursei și `SYSTEM_ADMIN`; altfel 403 `ACCESS_DENIED`.

    Args:
        repository: Accesul la rezervările din baza de date.
        current_user_id: Id-ul utilizatorului care face cererea.
    """

    def __init__(self, repository: ReservationRepository, current_user_id: int) -> None:
        self._repository = repository
        self._current_user_id = current_user_id
        self._current_role: Role | None = None

    @property
    def current_user_id(self) -> int:
        """Id-ul utilizatorului în numele căruia se face cererea."""
        return self._current_user_id

    def list_my_reservations(
        self, reservation_filter: ReservationFilter, page: int, size: int
    ) -> ReservationSummaryPage:
        """Întoarce o pagină din rezervările utilizatorului curent."""
        if self._role() not in REQUESTER_ROLES:
            raise ForbiddenError("Doar studenții și cercetătorii au rezervări proprii.")
        items, total = self._repository.find_page(reservation_filter, page, size)
        return ReservationSummaryPage(
            content=[ReservationSummary.model_validate(item) for item in items],
            page=PageMeta(
                page=page,
                size=size,
                total_elements=total,
                total_pages=math.ceil(total / size),
            ),
        )

    def get_reservation(self, reservation_id: int) -> ReservationOut:
        """Întoarce detaliile rezervării, 404 dacă nu există sau 403 fără drept de acces."""
        reservation = self._get_or_raise(reservation_id)
        if not self._can_view(reservation):
            raise ForbiddenError("Nu ai acces la această rezervare.")
        return self._to_out(reservation)

    def get_calendar(self, resource_id: int, start: datetime, end: datetime) -> ResourceCalendar:
        """Întoarce intervalele ocupate ale resursei în `[start, end)`, ordonate după început.

        Rezervările altor utilizatori apar fără id; `PENDING_ADMIN` apare ca `PENDING`.
        """
        resource = self._repository.find_resource(resource_id)
        if resource is None:
            raise NotFoundError(f"Resursa {resource_id} nu există.")
        entries = [
            self._reservation_entry(reservation)
            for reservation in self._repository.find_blocking_reservations(resource_id, start, end)
        ]
        entries += [
            CalendarEntry(
                start=block.start_at,
                # O mentenanță fără sfârșit ocupă tot restul intervalului cerut.
                end=block.end_at or end,
                type=CalendarEntryType.MAINTENANCE,
                own=False,
            )
            for block in self._repository.find_blocking_maintenance(resource_id, start, end)
        ]
        entries.sort(key=lambda entry: (entry.start, entry.end))
        return ResourceCalendar(
            resource=ResourceRef.model_validate(resource),
            start=start,
            end=end,
            rules=(
                UsageRuleSummary.model_validate(resource.usage_rule)
                if resource.usage_rule is not None
                else None
            ),
            entries=entries,
        )

    def _reservation_entry(self, reservation: Reservation) -> CalendarEntry:
        own = self._is_requester(reservation)
        if reservation.status == ReservationStatus.PENDING_ADMIN:
            entry_type = CalendarEntryType.PENDING
        else:
            entry_type = CalendarEntryType(reservation.status)
        return CalendarEntry(
            start=reservation.start_at,
            end=reservation.end_at,
            type=entry_type,
            own=own,
            reservation_id=reservation.id if own else None,
        )

    def _get_or_raise(self, reservation_id: int) -> Reservation:
        reservation = self._repository.find_by_id(reservation_id)
        if reservation is None:
            raise NotFoundError(f"Rezervarea {reservation_id} nu există.")
        return reservation

    def _can_view(self, reservation: Reservation) -> bool:
        return (
            self._is_requester(reservation)
            or self._is_coordinator(reservation)
            or reservation.resource.administrator_id == self._current_user_id
            or self._role() == Role.SYSTEM_ADMIN
        )

    def _is_requester(self, reservation: Reservation) -> bool:
        return reservation.requester_id == self._current_user_id

    def _is_coordinator(self, reservation: Reservation) -> bool:
        """Dacă utilizatorul curent coordonează echipa proiectului rezervării."""
        return reservation.project.team.coordinator_id == self._current_user_id

    def _role(self) -> Role | None:
        """Rolul utilizatorului curent, citit o singură dată pe cerere."""
        if self._current_role is None:
            user = self._repository.find_user(self._current_user_id)
            self._current_role = Role(user.role) if user is not None else None
        return self._current_role

    @staticmethod
    def _to_out(reservation: Reservation) -> ReservationOut:
        out = ReservationOut.model_validate(reservation)
        if reservation.cancelled_at is not None:
            cancelled_by = reservation.cancelled_by
            out.cancellation = Cancellation(
                cancelled_at=reservation.cancelled_at,
                cancelled_by=UserRef.model_validate(cancelled_by) if cancelled_by else None,
                reason=reservation.cancel_reason,
            )
        return out
