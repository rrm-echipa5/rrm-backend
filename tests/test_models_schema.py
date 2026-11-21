from collections.abc import Mapping

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.orm import Session

from app.db.models import Base


def _skip_alembic_version(
    name: str | None, type_: str, _parents: Mapping[str, str | None]
) -> bool:
    # Tabelul cu versiunea migrării aplicate există doar într-o bază creată de Alembic.
    return not (type_ == "table" and name == "alembic_version")


def test_models_match_the_database_schema(db_session: Session) -> None:
    # Pică dacă un model se schimbă fără migrare (sau schema fără model). Autogenerate compară
    # tabelele, coloanele (tip, NULL, valoare implicită), cheile, indexurile și constrângerile
    # UNIQUE. Nu vede vederile, constrângerile CHECK și EXCLUDE, condiția indexurilor parțiale
    # și formula coloanelor calculate; acestea se verifică manual, comparând `pg_dump` pe o
    # bază creată cu `alembic upgrade head` cu cel al bazei din `db/schema.sql`.
    context = MigrationContext.configure(
        db_session.connection(),
        opts={
            "compare_type": True,
            "compare_server_default": True,
            "include_name": _skip_alembic_version,
        },
    )

    assert compare_metadata(context, Base.metadata) == []
