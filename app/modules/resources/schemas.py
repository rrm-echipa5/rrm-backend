"""Schemele JSON ale resurselor, cu aceleași nume și limite ca în `rrm-api.yaml`."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Baza schemelor API: câmpuri camelCase în JSON, snake_case în Python."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class ResourceStatus(StrEnum):
    """Enumerarea `StareResursă`."""

    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    FAULTY = "FAULTY"


class ApprovalFlow(StrEnum):
    """Enumerarea `FluxAprobare`."""

    AUTO = "AUTO"
    COORDINATOR = "COORDINATOR"
    COORDINATOR_AND_ADMIN = "COORDINATOR_AND_ADMIN"


class CategoryCode(StrEnum):
    """Codurile categoriilor de resurse (enumerarea `CategorieResursă`)."""

    HARDWARE = "HARDWARE"
    HPC = "HPC"
    ROOM = "ROOM"
    MEASUREMENT_INSTRUMENT = "MEASUREMENT_INSTRUMENT"


class ResourceCategoryOut(ApiModel):
    """O categorie de resurse (`ResourceCategory`)."""

    id: int
    code: CategoryCode
    name: str


class CategoryRef(ApiModel):
    """Referința la categoria unei resurse (`CategoryRef`)."""

    id: int
    name: str


class UserRef(ApiModel):
    """Referința la un utilizator (`UserRef`)."""

    id: int
    name: str
    email: str | None = None


class ResourceSummary(ApiModel):
    """Resursa, așa cum apare în catalog (`ResourceSummary`)."""

    id: int
    name: str
    category: CategoryRef
    location: str | None
    status: ResourceStatus
    approval_flow: ApprovalFlow
    tags: list[str]


class ResourceDetail(ResourceSummary):
    """Fișa resursei (`ResourceDetail`), fără regulile și fișierele din KAN-88 și KAN-89."""

    description: str | None
    specifications: dict[str, str]
    administrator: UserRef
    check_in_qr_code: str | None
    created_at: datetime
    updated_at: datetime


class PageMeta(ApiModel):
    """Datele de paginare (`PageMeta`)."""

    page: int
    size: int
    total_elements: int
    total_pages: int


class ResourceSummaryPage(ApiModel):
    """O pagină din catalog (`ResourceSummaryPage`)."""

    content: list[ResourceSummary]
    page: PageMeta


Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
SpecificationValue = Annotated[str, StringConstraints(max_length=500)]


class ResourceWriteRequest(ApiModel):
    """Datele fișei resursei, la creare și la modificare (`ResourceWriteRequest`)."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
    category_id: int = Field(ge=1)
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        None
    )
    description: Annotated[str, StringConstraints(max_length=4000)] | None = None
    specifications: dict[str, SpecificationValue] = Field(default_factory=dict)
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    approval_flow: ApprovalFlow
    administrator_id: int | None = Field(default=None, ge=1)
