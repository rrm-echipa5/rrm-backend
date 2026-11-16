from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import FieldError, ValidationFailedError
from app.db.session import get_session
from app.modules.reservations.models import ReservationStatus
from app.modules.reservations.repository import ReservationFilter, ReservationRepository
from app.modules.reservations.schemas import ReservationOut, ReservationSummaryPage
from app.modules.reservations.service import ReservationService
from app.modules.resources.router import PROBLEM_RESPONSES

router = APIRouter(tags=["Rezervări"])

ReservationId = Annotated[int, Path(ge=1, description="Identificatorul rezervării.")]


def get_reservation_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReservationService:
    """Construiește serviciul de rezervări pentru cererea curentă."""
    return ReservationService(ReservationRepository(session), settings.demo_user_id)


Service = Annotated[ReservationService, Depends(get_reservation_service)]


@router.get("/users/me/reservations", responses=PROBLEM_RESPONSES)
def list_my_reservations(  # noqa: PLR0913 - parametrii de filtrare din rrm-api.yaml
    service: Service,
    statuses: Annotated[list[ReservationStatus] | None, Query(alias="status")] = None,
    from_: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    to: Annotated[AwareDatetime | None, Query()] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[
        str, Query(pattern=r"^(id|start|end|status|createdAt)(,(asc|desc))?$")
    ] = "start,desc",
) -> ReservationSummaryPage:
    """Rezervările utilizatorului curent, paginate, cu filtre pe status și interval.

    `status` se poate repeta; `from` păstrează rezervările care se termină după acel moment,
    iar `to` pe cele care încep înainte de el. Roluri: `STUDENT`, `RESEARCHER`.
    """
    if from_ is not None and to is not None and to <= from_:
        raise ValidationFailedError(
            [FieldError(field="to", message="Sfârșitul intervalului trebuie să fie după început.")]
        )
    sort_field, _, direction = sort.partition(",")
    reservation_filter = ReservationFilter(
        requester_id=service.current_user_id,
        statuses=tuple(statuses or ()),
        ends_after=from_,
        starts_before=to,
        sort_field=sort_field,
        descending=direction == "desc",
    )
    return service.list_my_reservations(reservation_filter, page, size)


@router.get("/reservations/{reservation_id}", responses=PROBLEM_RESPONSES)
def get_reservation(reservation_id: ReservationId, service: Service) -> ReservationOut:
    """Detaliile rezervării, cu istoricul aprobărilor.

    Roluri: solicitantul, coordonatorul echipei proiectului, administratorul resursei,
    `SYSTEM_ADMIN`.
    """
    return service.get_reservation(reservation_id)
