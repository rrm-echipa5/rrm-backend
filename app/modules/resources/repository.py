from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, Text, cast, func, or_, select, text
from sqlalchemy.orm import Session

from app.modules.resources.models import Resource, ResourceCategory
from app.modules.users.models import User

# Câmpurile după care se poate sorta catalogul (`sort=câmp,asc|desc`).
SORTABLE_COLUMNS = {
    "id": Resource.id,
    "name": Resource.name,
    "location": Resource.location,
    "status": Resource.status,
    "createdAt": Resource.created_at,
}

# Rezervările care blochează scoaterea resursei din catalog (409 RESOURCE_HAS_RESERVATIONS).
ACTIVE_RESERVATIONS_QUERY = text(
    """
    SELECT EXISTS (
        SELECT 1 FROM reservations
        WHERE resource_id = :resource_id
          AND status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS')
          AND end_at > now()
    )
    """
)

# Resursele dintre cele date pentru care utilizatorul are o certificare valabilă (`ACTIVE`):
# nerevocată și neexpirată, după vederea `certification_statuses`.
CERTIFIED_RESOURCES_QUERY = text(
    """
    SELECT resource_id FROM certification_statuses
    WHERE user_id = :user_id
      AND resource_id = ANY(:resource_ids)
      AND status = 'ACTIVE'
    """
)


@dataclass(frozen=True)
class ResourceFilter:
    """Filtrele și sortarea catalogului de resurse.

    `tags` păstrează doar resursele care au toate tag-urile cerute, iar `administrator_id`
    doar resursele administrate de utilizatorul dat (filtrul `administeredByMe`).
    """

    category_id: int | None = None
    statuses: tuple[str, ...] = ()
    query: str | None = None
    tags: tuple[str, ...] = ()
    administrator_id: int | None = None
    sort_field: str = "name"
    descending: bool = False


class ResourceRepository:
    """Citește și scrie resursele și categoriile în PostgreSQL.

    Args:
        session: Sesiunea SQLAlchemy a cererii curente.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_categories(self) -> Sequence[ResourceCategory]:
        """Întoarce toate categoriile, în ordinea id-ului."""
        return self._session.scalars(select(ResourceCategory).order_by(ResourceCategory.id)).all()

    def category_exists(self, category_id: int) -> bool:
        """Verifică dacă există categoria cu id-ul dat."""
        return self._session.get(ResourceCategory, category_id) is not None

    def user_exists(self, user_id: int) -> bool:
        """Verifică dacă există utilizatorul cu id-ul dat."""
        return self.find_user(user_id) is not None

    def find_user(self, user_id: int) -> User | None:
        """Întoarce utilizatorul cu id-ul dat sau `None`."""
        return self._session.get(User, user_id)

    def find_page(
        self, resource_filter: ResourceFilter, page: int, size: int
    ) -> tuple[Sequence[Resource], int]:
        """Întoarce o pagină din catalog și numărul total de resurse care trec de filtre."""
        statement = self._filtered(resource_filter)
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        column = SORTABLE_COLUMNS[resource_filter.sort_field]
        order = column.desc() if resource_filter.descending else column.asc()
        items = self._session.scalars(
            statement.order_by(order, Resource.id).offset(page * size).limit(size)
        ).all()
        return items, total

    def find_by_id(self, resource_id: int) -> Resource | None:
        """Întoarce resursa nestearsă cu id-ul dat sau `None`."""
        statement = select(Resource).where(
            Resource.id == resource_id, Resource.deleted_at.is_(None)
        )
        return self._session.scalars(statement).first()

    def certified_resource_ids(self, user_id: int, resource_ids: Sequence[int]) -> set[int]:
        """Întoarce id-urile resurselor pentru care utilizatorul are o certificare valabilă."""
        if not resource_ids:
            return set()
        rows = self._session.scalars(
            CERTIFIED_RESOURCES_QUERY,
            {"user_id": user_id, "resource_ids": list(resource_ids)},
        )
        return set(rows)

    def has_active_reservations(self, resource_id: int) -> bool:
        """Verifică dacă resursa are cereri în așteptare sau rezervări care nu s-au încheiat."""
        result = self._session.scalar(ACTIVE_RESERVATIONS_QUERY, {"resource_id": resource_id})
        return bool(result)

    def add(self, resource: Resource) -> None:
        """Adaugă o resursă nouă și obține id-ul ei din baza de date."""
        self._session.add(resource)
        self._session.flush()

    def commit_and_refresh(self, resource: Resource) -> None:
        """Salvează modificările și reîncarcă resursa, cu categoria și administratorul."""
        self._session.commit()
        self._session.refresh(resource)

    @staticmethod
    def _filtered(resource_filter: ResourceFilter) -> Select[Resource]:
        statement = select(Resource).where(Resource.deleted_at.is_(None))
        if resource_filter.category_id is not None:
            statement = statement.where(Resource.category_id == resource_filter.category_id)
        if resource_filter.statuses:
            statement = statement.where(Resource.status.in_(resource_filter.statuses))
        if resource_filter.query:
            pattern = f"%{resource_filter.query}%"
            statement = statement.where(
                or_(
                    Resource.name.ilike(pattern),
                    Resource.location.ilike(pattern),
                    cast(Resource.specifications, Text).ilike(pattern),
                )
            )
        if resource_filter.tags:
            statement = statement.where(Resource.tags.contains(list(resource_filter.tags)))
        if resource_filter.administrator_id is not None:
            statement = statement.where(
                Resource.administrator_id == resource_filter.administrator_id
            )
        return statement
