"""${message}

Revizia: ${up_revision}
Revizia anterioară: ${down_revision | comma,n}
Creată: ${create_date}
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """Aplică modificările acestei revizii."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Anulează modificările acestei revizii."""
    ${downgrades if downgrades else "pass"}
