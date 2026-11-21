import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.modules.notifications.models import Notification, NotificationChannel, NotificationType
from app.modules.reservations.models import Reservation, ReservationStatus
from app.modules.reservations.repository import ReservationFilter, ReservationRepository
from app.modules.reservations.schemas import (
    Cancellation,
    ReservationOut,
    ReservationSummary,
    ReservationSummaryPage,
)
from app.modules.resources.schemas import PageMeta, UserRef
from app.modules.users.models import Role

# Rolurile care au rezervări proprii (`GET /users/me/reservations` din rrm-api.yaml).
REQUESTER_ROLES = frozenset({Role.STUDENT, Role.RESEARCHER})

# Stările din care se poate anula (extensia „Anulare rezervare” din rrm-api.yaml).
CANCELLABLE_STATUSES = frozenset(
    {ReservationStatus.PENDING, ReservationStatus.PENDING_ADMIN, ReservationStatus.CONFIRMED}
)

# Orele din textul notificărilor se afișează în ora României, ca în restul interfeței.
LOCAL_TIMEZONE = ZoneInfo("Europe/Bucharest")


class ReservationService:
    """Regulile de business pentru rezervările unui utilizator (KAN-77, KAN-78).

    Până la autentificare (KAN-64), utilizatorul curent este cel din setarea
    `RRM_DEMO_USER_ID`. Drepturile urmează `rrm-api.yaml`: lista proprie o văd `STUDENT` și
    `RESEARCHER`, detaliile unei rezervări solicitantul, coordonatorul echipei proiectului,
    administratorul resursei și `SYSTEM_ADMIN`, iar rezervarea o anulează doar solicitantul și
    coordonatorul; altfel 403 `ACCESS_DENIED`.

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

    def cancel_reservation(self, reservation_id: int, reason: str | None) -> ReservationOut:
        """Anulează o cerere în așteptare sau o rezervare confirmată (KAN-78).

        Intervalul se eliberează și orele unei rezervări confirmate revin în bugetul
        proiectului singure: constrângerea de suprapunere și vederea `project_budgets` iau în
        calcul doar rezervările active. Aprobatorii implicați primesc o notificare.
        """
        reservation = self._get_or_raise(reservation_id, for_update=True)
        if not (self._is_requester(reservation) or self._is_coordinator(reservation)):
            raise ForbiddenError(
                "Doar solicitantul și coordonatorul echipei pot anula rezervarea."
            )
        if reservation.status not in CANCELLABLE_STATUSES:
            raise ConflictError(
                "INVALID_STATE",
                f"Rezervarea are statusul {reservation.status} și nu mai poate fi anulată.",
            )
        approvers = self._approvers_to_notify(reservation)
        # Numele celui care anulează se citește o singură dată, pentru toate notificările.
        canceller = self._repository.find_user(self._current_user_id)
        canceller_name = canceller.name if canceller else None
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = datetime.now(UTC)
        reservation.cancelled_by_id = self._current_user_id
        reservation.cancel_reason = reason or None
        self._repository.add_notifications(
            [
                self._cancellation_notice(reservation, approver_id, canceller_name)
                for approver_id in approvers
            ]
        )
        self._repository.commit_and_refresh(reservation)
        return self._to_out(reservation)

    def _approvers_to_notify(self, reservation: Reservation) -> list[int]:
        """Aprobatorii care au decis deja și cel a cărui decizie se aștepta.

        Cel care anulează nu se notifică pe sine.
        """
        approver_ids = [approval.approver_id for approval in reservation.approvals]
        if reservation.status == ReservationStatus.PENDING:
            approver_ids.append(reservation.project.team.coordinator_id)
        elif reservation.status == ReservationStatus.PENDING_ADMIN:
            approver_ids.append(reservation.resource.administrator_id)
        return [
            approver_id
            for approver_id in dict.fromkeys(approver_ids)
            if approver_id != self._current_user_id
        ]

    @staticmethod
    def _cancellation_notice(
        reservation: Reservation, recipient_id: int, canceller_name: str | None
    ) -> Notification:
        start = reservation.start_at.astimezone(LOCAL_TIMEZONE)
        end = reservation.end_at.astimezone(LOCAL_TIMEZONE)
        body = (
            f"Rezervarea pentru {reservation.resource.name} din {start:%d.%m.%Y}, "
            f"{start:%H:%M}-{end:%H:%M} (solicitant: {reservation.requester.name}) "
            f"a fost anulată{f' de {canceller_name}' if canceller_name else ''}."
        )
        if reservation.cancel_reason:
            body += f" Motiv: {reservation.cancel_reason}"
        return Notification(
            recipient_id=recipient_id,
            channel=NotificationChannel.IN_APP,
            type=NotificationType.RESERVATION_CANCELLED,
            title=f"Rezervare anulată: {reservation.resource.name}",
            body=body,
            reservation_id=reservation.id,
        )

    def _get_or_raise(self, reservation_id: int, *, for_update: bool = False) -> Reservation:
        if for_update:
            reservation = self._repository.find_by_id_for_update(reservation_id)
        else:
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
