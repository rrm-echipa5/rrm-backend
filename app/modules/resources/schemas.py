"""Schemele JSON ale resurselor, cu aceleași nume și limite ca în `rrm-api.yaml`."""

from datetime import date, datetime
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
    # Nivelul de certificare cerut; `None` dacă resursa nu cere certificare.
    required_certification_level: int | None = None
    # Dacă utilizatorul curent are o certificare valabilă pentru resursă; se completează în
    # serviciu, din vederea `certification_statuses`.
    user_certified: bool = False


class UsageRuleOut(ApiModel):
    """Regulile de utilizare ale resursei, cu fluxul de aprobare (`UsageRule`)."""

    min_duration_minutes: int
    max_duration_minutes: int
    break_between_minutes: int
    check_in_deadline_minutes: int
    required_certification_level: int | None
    approval_flow: ApprovalFlow
    updated_at: datetime
    updated_by: UserRef | None


class ResourceFileType(StrEnum):
    """Tipul unui fișier al resursei."""

    MANUAL = "MANUAL"
    PHOTO = "PHOTO"


class ResourceFileOut(ApiModel):
    """Un manual PDF sau o poză a resursei (`ResourceFile`)."""

    id: int
    type: ResourceFileType
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    url: str
    uploaded_at: datetime


class ResourceDetail(ResourceSummary):
    """Fișa resursei (`ResourceDetail`), fără mentenanță.

    `files` este obligatoriu în contract; până la încărcarea fișierelor (KAN-89) lista e goală,
    ca frontend-ul să poată folosi câmpul de pe acum.
    """

    description: str | None
    specifications: dict[str, str]
    administrator: UserRef
    usage_rule: UsageRuleOut
    files: list[ResourceFileOut] = Field(default_factory=list)
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


class ResourceRef(ApiModel):
    """Referința la o resursă (`ResourceRef`)."""

    id: int
    name: str


class CertificationStatus(StrEnum):
    """Starea unei certificări (`CertificationStatus`), din vederea `certification_statuses`."""

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class CertificationOut(ApiModel):
    """Certificarea unui utilizator pentru o resursă (`Certification`)."""

    id: int
    user: UserRef
    resource: ResourceRef
    level: int
    status: CertificationStatus
    granted_at: datetime
    granted_by: UserRef
    expires_at: date | None
    revoked_at: datetime | None
    revoke_reason: str | None


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
