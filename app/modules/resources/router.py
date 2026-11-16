from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import PROBLEM_MEDIA_TYPE, Problem
from app.db.session import get_session
from app.modules.resources.repository import ResourceFilter, ResourceRepository
from app.modules.resources.schemas import (
    ResourceCategoryOut,
    ResourceDetail,
    ResourceStatus,
    ResourceSummaryPage,
    ResourceWriteRequest,
)
from app.modules.resources.service import ResourceService

router = APIRouter(tags=["Resurse"])

PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    code: {"model": Problem, "content": {PROBLEM_MEDIA_TYPE: {}}, "description": description}
    for code, description in [
        (status.HTTP_400_BAD_REQUEST, "Corpul sau parametrii cererii sunt invalizi."),
        (status.HTTP_403_FORBIDDEN, "Rolul utilizatorului nu permite operația."),
        (status.HTTP_404_NOT_FOUND, "Resursa nu există."),
        (status.HTTP_409_CONFLICT, "Starea resursei nu permite operația."),
    ]
}

ResourceId = Annotated[int, Path(ge=1, description="Identificatorul resursei.")]


def get_resource_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResourceService:
    """Construiește serviciul de resurse pentru cererea curentă."""
    return ResourceService(ResourceRepository(session), settings.demo_user_id)


Service = Annotated[ResourceService, Depends(get_resource_service)]


@router.get("/resource-categories")
def list_resource_categories(service: Service) -> list[ResourceCategoryOut]:
    """Categoriile de resurse, pentru filtrarea catalogului și formularul fișei."""
    return service.list_categories()


@router.get("/resources", responses=PROBLEM_RESPONSES)
def list_resources(  # noqa: PLR0913 - parametrii de filtrare din rrm-api.yaml
    service: Service,
    category_id: Annotated[int | None, Query(alias="categoryId", ge=1)] = None,
    statuses: Annotated[list[ResourceStatus] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    tags: Annotated[list[str] | None, Query(alias="tag", max_length=20)] = None,
    administered_by_me: Annotated[bool, Query(alias="administeredByMe")] = False,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[
        str, Query(pattern=r"^(id|name|location|status|createdAt)(,(asc|desc))?$")
    ] = "name,asc",
) -> ResourceSummaryPage:
    """Catalogul de resurse, paginat, cu filtre pe categorie, stare, text, tag-uri și admin.

    `tag` se poate repeta, iar resursa trebuie să aibă toate tag-urile cerute;
    `administeredByMe=true` păstrează doar resursele administrate de utilizatorul curent.
    """
    sort_field, _, direction = sort.partition(",")
    resource_filter = ResourceFilter(
        category_id=category_id,
        statuses=tuple(statuses or ()),
        query=q.strip() if q else None,
        tags=tuple(dict.fromkeys(tag.strip() for tag in tags or () if tag.strip())),
        administrator_id=service.current_user_id if administered_by_me else None,
        sort_field=sort_field,
        descending=direction == "desc",
    )
    return service.list_resources(resource_filter, page, size)


@router.post("/resources", status_code=status.HTTP_201_CREATED, responses=PROBLEM_RESPONSES)
def create_resource(
    body: ResourceWriteRequest, service: Service, request: Request, response: Response
) -> ResourceDetail:
    """Adaugă o resursă în catalog, cu regulile implicite; `Location` conține URI-ul ei.

    Roluri: `RESOURCE_ADMIN`, `SYSTEM_ADMIN`; alt administrator decât utilizatorul curent
    poate alege doar `SYSTEM_ADMIN`.
    """
    resource = service.create_resource(body)
    response.headers["Location"] = str(request.url_for("get_resource", resource_id=resource.id))
    return resource


@router.get("/resources/{resource_id}", responses=PROBLEM_RESPONSES)
def get_resource(resource_id: ResourceId, service: Service) -> ResourceDetail:
    """Fișa resursei."""
    return service.get_resource(resource_id)


@router.put("/resources/{resource_id}", responses=PROBLEM_RESPONSES)
def update_resource(
    resource_id: ResourceId, body: ResourceWriteRequest, service: Service
) -> ResourceDetail:
    """Modifică fișa resursei.

    Roluri: administratorul resursei, `SYSTEM_ADMIN`; administratorul îl schimbă doar
    `SYSTEM_ADMIN`.
    """
    return service.update_resource(resource_id, body)


@router.delete(
    "/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=PROBLEM_RESPONSES,
)
def delete_resource(resource_id: ResourceId, service: Service) -> None:
    """Scoate resursa din catalog (ștergere logică). Rol: `SYSTEM_ADMIN`."""
    service.delete_resource(resource_id)
