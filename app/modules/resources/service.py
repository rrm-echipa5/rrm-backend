import math
import secrets
import uuid
from datetime import UTC, datetime

from app.core.errors import ConflictError, FieldError, NotFoundError, ValidationFailedError
from app.modules.resources.models import Resource
from app.modules.resources.repository import ResourceFilter, ResourceRepository
from app.modules.resources.schemas import (
    PageMeta,
    ResourceCategoryOut,
    ResourceDetail,
    ResourceStatus,
    ResourceSummary,
    ResourceSummaryPage,
    ResourceWriteRequest,
)


class ResourceService:
    """Regulile de business pentru catalogul de resurse (aplicația inițială, KAN-124).

    Până la autentificare (KAN-64), utilizatorul curent este cel din setarea
    `RRM_DEMO_USER_ID`; verificarea rolurilor se adaugă în KAN-88.

    Args:
        repository: Accesul la resursele din baza de date.
        current_user_id: Id-ul utilizatorului care face cererea.
    """

    def __init__(self, repository: ResourceRepository, current_user_id: int) -> None:
        self._repository = repository
        self._current_user_id = current_user_id

    def list_categories(self) -> list[ResourceCategoryOut]:
        """Întoarce categoriile de resurse."""
        return [ResourceCategoryOut.model_validate(c) for c in self._repository.list_categories()]

    def list_resources(
        self, resource_filter: ResourceFilter, page: int, size: int
    ) -> ResourceSummaryPage:
        """Întoarce o pagină din catalog."""
        items, total = self._repository.find_page(resource_filter, page, size)
        return ResourceSummaryPage(
            content=[ResourceSummary.model_validate(item) for item in items],
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
        """Adaugă o resursă în catalog, cu starea `ACTIVE` și un cod QR unic pentru check-in."""
        administrator_id = request.administrator_id or self._current_user_id
        self._validate_references(request.category_id, administrator_id)
        resource = Resource(
            status=ResourceStatus.ACTIVE,
            administrator_id=administrator_id,
            check_in_qr_code=f"RRM-NEW-{uuid.uuid4().hex}",
        )
        self._apply(resource, request)
        self._repository.add(resource)
        resource.check_in_qr_code = f"RRM-R{resource.id}-{secrets.token_hex(3)}"
        self._repository.commit_and_refresh(resource)
        return self._to_detail(resource)

    def update_resource(self, resource_id: int, request: ResourceWriteRequest) -> ResourceDetail:
        """Modifică datele descriptive ale resursei; starea nu se schimbă aici."""
        resource = self._get_or_raise(resource_id)
        administrator_id = request.administrator_id or resource.administrator_id
        self._validate_references(request.category_id, administrator_id)
        self._apply(resource, request)
        resource.administrator_id = administrator_id
        resource.updated_at = datetime.now(UTC)
        self._repository.commit_and_refresh(resource)
        return self._to_detail(resource)

    def delete_resource(self, resource_id: int) -> None:
        """Scoate resursa din catalog (ștergere logică), dacă nu are rezervări active."""
        resource = self._get_or_raise(resource_id)
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
        # Codul QR de check-in este vizibil doar pentru administratorul resursei.
        if resource.administrator_id != self._current_user_id:
            detail.check_in_qr_code = None
        return detail
