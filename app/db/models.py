"""Importă toate modelele, ca `Base.metadata` să conțină toate tabelele din `db/schema.sql`.

Alembic (`migrations/env.py`) și testul care compară modelele cu schema se bazează pe acest
modul; un model nou se adaugă și aici.
"""

from app.db.base import Base
from app.modules.auth import models as auth
from app.modules.certifications import models as certifications
from app.modules.maintenance import models as maintenance
from app.modules.notifications import models as notifications
from app.modules.projects import models as projects
from app.modules.reservations import models as reservations
from app.modules.resources import models as resources
from app.modules.settings import models as settings
from app.modules.users import models as users

__all__ = [
    "Base",
    "auth",
    "certifications",
    "maintenance",
    "notifications",
    "projects",
    "reservations",
    "resources",
    "settings",
    "users",
]
