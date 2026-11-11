from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clasa de bază a modelelor SQLAlchemy; tabelele sunt cele din `db/schema.sql`."""
