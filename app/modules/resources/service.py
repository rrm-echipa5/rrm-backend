import math
import secrets
import uuid
from datetime import UTC, datetime

from app.core.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from app.modules.resources.models import Resource, UsageRule
from app.modules.resources.repository import ResourceFilter, ResourceRepository
from app.modules.resources.schemas import (
    CertificationOut,
    PageMeta,
    ResourceCategoryOut,
    ResourceDetail,
    ResourceRef,
    ResourceStatus,
    ResourceSummary,
    ResourceSummaryPage,
    ResourceWriteRequest,
    UserRef,
)
from app.modules.users.models import Role

# Rolurile care pot adăuga resurse în catalog.
CATALOG_EDITOR_ROLES = frozenset({Role.RESOURCE_ADMIN, Role.SYSTEM_ADMIN})


class ResourceService:
    """Regulile de business pentru catalogul de resurse (aplicația inițială, KAN-124).

    Până la autentificare (KAN-64), utilizatorul curent este cel din setarea
    `RRM_DEMO_USER_ID`. Drepturile urmează `rrm-api.yaml`: adaugă resurse doar
    `RESOURCE_ADMIN` și `SYSTEM_ADMIN`, modifică fișa administratorul resursei sau
    `SYSTEM_ADMIN`, iar administratorul resursei îl schimbă și resursa o scoate din catalog
    doar `SYSTEM_ADMIN`; altfel răspunsul este 403 `ACCESS_DENIED`.

    Args:
        repository: Accesul la resursele din baza de date.
        current_user_id: Id-ul utilizatorului care face cererea.
    """

    def __init__(self, repository: ResourceRepository, current_user_id: int) -> None:
        self._repository = repository
        self._current_user_id = current_user_id
        self._current_role: Role | None = None

    @property
    def current_user_id(self) -> int:
        """Id-ul utilizatorului în numele căruia se face cererea."""
        return self._current_user_id

    def list_categories(self) -> list[ResourceCategoryOut]:
        """Întoarce categoriile de resurse."""
        return [ResourceCategoryOut.model_validate(c) for c in self._repository.list_categories()]

    def list_my_certifications(self) -> list[CertificationOut]:
        """Întoarce certificările utilizatorului curent, pentru toate resursele."""
        return [
            CertificationOut(
                id=row["id"],
                user=UserRef(id=row["user_id"], name=row["user_name"], email=row["user_email"]),
                resource=ResourceRef(id=row["resource_id"], name=row["resource_name"]),
                level=row["level"],
                status=row["status"],
                granted_at=row["granted_at"],
                granted_by=UserRef(
                    id=row["granted_by_id"],
                    name=row["granted_by_name"],
                    email=row["granted_by_email"],
                ),
                expires_at=row["expires_at"],
                revoked_at=row["revoked_at"],
                revoke_reason=row["revoke_reason"],
            )
            for row in self._repository.list_user_certifications(self._current_user_id)
        ]

    def list_resources(
        self, resource_filter: ResourceFilter, page: int, size: int
    ) -> ResourceSummaryPage:
        """Întoarce o pagină din catalog, cu `userCertified` pentru utilizatorul curent."""
        items, total = self._repository.find_page(resource_filter, page, size)
        certified = self._repository.certified_resource_ids(
            self._current_user_id, [item.id for item in items]
        )
        content = []
        for item in items:
            summary = ResourceSummary.model_validate(item)
            summary.user_certified = item.id in certified
            content.append(summary)
        return ResourceSummaryPage(
            content=content,
            page=PageMeta(
                page=page,
                size=size,
                total_elements=total,
                total_pages=math.ceil(total / size),
            ),
        )

    def get_resource(self, resource_id: int) -> ResourceDetail:
        """Întoarce fișa resursei sau 404 dacă nu există."""
        return self._to_detail(self._get_or_raise(resource_id))

    def create_resource(self, request: ResourceWriteRequest) -> ResourceDetail:
        """Adaugă o resursă în catalog, cu starea `ACTIVE` și regulile de utilizare implicite.

        Primește și un cod QR unic pentru check-in.
        """
        if self._role() not in CATALOG_EDITOR_ROLES:
            raise ForbiddenError("Doar administratorii de resurse pot adăuga resurse în catalog.")
        administrator_id = request.administrator_id or self._current_user_id
        self._check_administrator_change(self._current_user_id, administrator_id)
        self._validate_references(request.category_id, administrator_id)
        resource = Resource(
            status=ResourceStatus.ACTIVE,
            administrator_id=administrator_id,
            check_in_qr_code=f"RRM-NEW-{uuid.uuid4().hex}",
            usage_rule=UsageRule(
                updated_at=datetime.now(UTC), updated_by_id=self._current_user_id
            ),
        )
        self._apply(resource, request)
        self._repository.add(resource)
        resource.check_in_qr_code = f"RRM-R{resource.id}-{secrets.token_hex(3)}"
        self._repository.commit_and_refresh(resource)
        return self._to_detail(resource)

    def update_resource(self, resource_id: int, request: ResourceWriteRequest) -> ResourceDetail:
        """Modifică datele descriptive ale resursei; starea nu se schimbă aici."""
        resource = self._get_or_raise(resource_id)
        if resource.administrator_id != self._current_user_id and not self._is_system_admin():
            raise ForbiddenError("Doar administratorul resursei poate modifica fișa ei.")
        administrator_id = request.administrator_id or resource.administrator_id
        self._check_administrator_change(resource.administrator_id, administrator_id)
        self._validate_references(request.category_id, administrator_id)
        self._apply(resource, request)
        resource.administrator_id = administrator_id
        resource.updated_at = datetime.now(UTC)
        self._repository.commit_and_refresh(resource)
        return self._to_detail(resource)

    def delete_resource(self, resource_id: int) -> None:
        """Scoate resursa din catalog (ștergere logică), dacă nu are rezervări active."""
        resource = self._get_or_raise(resource_id)
        if not self._is_system_admin():
            raise ForbiddenError(
                "Doar administratorul de sistem poate scoate resurse din catalog."
            )
        if self._repository.has_active_reservations(resource_id):
            raise ConflictError(
                "RESOURCE_HAS_RESERVATIONS",
                f"Resursa „{resource.name}” are cereri în așteptare sau rezervări viitoare. "
                "Anulează-le înainte de a o scoate din catalog.",
            )
        resource.deleted_at = datetime.now(UTC)
        self._repository.commit_and_refresh(resource)

    def _get_or_raise(self, resource_id: int) -> Resource:
        resource = self._repository.find_by_id(resource_id)
        if resource is None:
            raise NotFoundError(f"Resursa {resource_id} nu există.")
        return resource

    def _role(self) -> Role | None:
        """Rolul utilizatorului curent, citit o singură dată pe cerere."""
        if self._current_role is None:
            user = self._repository.find_user(self._current_user_id)
            self._current_role = Role(user.role) if user is not None else None
        return self._current_role

    def _is_system_admin(self) -> bool:
        return self._role() == Role.SYSTEM_ADMIN

    def _check_administrator_change(self, current_id: int, requested_id: int) -> None:
        if requested_id != current_id and not self._is_system_admin():
            raise ForbiddenError(
                "Doar administratorul de sistem poate schimba administratorul resursei."
            )

    def _validate_references(self, category_id: int, administrator_id: int) -> None:
        errors = []
        if not self._repository.category_exists(category_id):
            errors.append(FieldError(field="categoryId", message="Categoria nu există."))
        if not self._repository.user_exists(administrator_id):
            errors.append(FieldError(field="administratorId", message="Utilizatorul nu există."))
        if errors:
            raise ValidationFailedError(errors)

    @staticmethod
    def _apply(resource: Resource, request: ResourceWriteRequest) -> None:
        resource.name = request.name
        resource.category_id = request.category_id
        resource.location = request.location or None
        resource.description = request.description or None
        resource.specifications = dict(request.specifications)
        resource.tags = list(dict.fromkeys(request.tags))
        resource.approval_flow = request.approval_flow

    def _to_detail(self, resource: Resource) -> ResourceDetail:
        detail = ResourceDetail.model_validate(resource)
        detail.user_certified = resource.id in self._repository.certified_resource_ids(
            self._current_user_id, [resource.id]
        )
        # Codul QR de check-in este vizibil doar pentru administratorul resursei.
        if resource.administrator_id != self._current_user_id:
            detail.check_in_qr_code = None
        return detail
