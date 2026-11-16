"""Schema inițială, aceeași ca `db/schema.sql`.

Revizia: 0001
Revizia anterioară: niciuna
Creată: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Vederile folosite de API; interogările sunt cele din `db/schema.sql`, doar rupte pe mai
# multe rânduri.
PROJECT_BUDGETS_VIEW = """
CREATE VIEW project_budgets AS
SELECT p.id,
       p.team_id,
       p.title,
       p.budget_hours,
       coalesce(sum(r.hours) FILTER (
           WHERE r.status IN ('CONFIRMED', 'IN_PROGRESS', 'COMPLETED')), 0)
           AS used_hours,
       p.budget_hours
           - coalesce(sum(r.hours) FILTER (
               WHERE r.status IN ('CONFIRMED', 'IN_PROGRESS', 'COMPLETED')), 0)
           AS remaining_hours
FROM projects p
LEFT JOIN reservations r ON r.project_id = p.id
GROUP BY p.id
"""

CERTIFICATION_STATUSES_VIEW = """
CREATE VIEW certification_statuses AS
SELECT c.*,
       CASE WHEN c.revoked_at IS NOT NULL THEN 'REVOKED'
            WHEN c.expires_at IS NOT NULL AND c.expires_at < current_date THEN 'EXPIRED'
            ELSE 'ACTIVE' END AS status
FROM certifications c
"""

# Tabelele în ordinea din `db/schema.sql`, în care fiecare tabel apare după cele pe care le referă.
TABLES = (
    "users",
    "two_factor_challenges",
    "trusted_devices",
    "refresh_tokens",
    "teams",
    "team_members",
    "projects",
    "resource_categories",
    "resources",
    "usage_rules",
    "resource_files",
    "certifications",
    "maintenance_blocks",
    "reservations",
    "approvals",
    "notifications",
    "app_settings",
)


def upgrade() -> None:
    """Creează extensia, tabelele, indexurile și vederile din `db/schema.sql`."""
    # Constrângerile de excludere combină egalitatea pe resource_id cu suprapunerea de
    # intervale, deci au nevoie de btree_gist.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    _create_users_and_auth()
    _create_teams_and_projects()
    _create_resources()
    _create_maintenance_and_reservations()
    _create_notifications_and_settings()
    op.execute(PROJECT_BUDGETS_VIEW)
    op.execute(CERTIFICATION_STATUSES_VIEW)


def downgrade() -> None:
    """Șterge vederile, tabelele (în ordine inversă) și extensia."""
    op.execute("DROP VIEW certification_statuses")
    op.execute("DROP VIEW project_budgets")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS btree_gist")


def _create_users_and_auth() -> None:
    """Utilizatorii și tabelele autentificării."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "two_factor_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("totp_secret", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "role IN ('STUDENT', 'RESEARCHER', 'RESOURCE_ADMIN', 'SYSTEM_ADMIN')",
            name="users_role_check",
        ),
        sa.CheckConstraint(
            "NOT two_factor_enabled OR totp_secret IS NOT NULL", name="users_totp_ck"
        ),
    )
    op.create_index("users_email_uq", "users", [sa.literal_column("lower(email)")], unique=True)

    op.create_table(
        "two_factor_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 5", name="two_factor_challenges_attempts_check"
        ),
    )
    op.create_index("two_factor_challenges_user_idx", "two_factor_challenges", ["user_id"])

    op.create_table(
        "trusted_devices",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("trusted_devices_user_idx", "trusted_devices", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("refresh_tokens_user_idx", "refresh_tokens", ["user_id"])


def _create_teams_and_projects() -> None:
    """Echipele, membrii lor și proiectele cu buget de ore."""
    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("coordinator_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["coordinator_id"], ["users.id"]),
        sa.UniqueConstraint("name"),
    )
    op.create_index("teams_coordinator_idx", "teams", ["coordinator_id"])

    op.create_table(
        "team_members",
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("team_members_user_idx", "team_members", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("budget_hours", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.CheckConstraint("budget_hours >= 0", name="projects_budget_hours_check"),
        sa.UniqueConstraint("team_id", "title", name="projects_team_id_title_key"),
    )


def _create_resources() -> None:
    """Resursele, regulile de utilizare, fișierele și certificările."""
    op.create_table(
        "resource_categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint(
            "code IN ('HARDWARE', 'HPC', 'ROOM', 'MEASUREMENT_INSTRUMENT')",
            name="resource_categories_code_check",
        ),
    )

    op.create_table(
        "resources",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "specifications",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("status", sa.Text(), server_default="ACTIVE", nullable=False),
        sa.Column("approval_flow", sa.Text(), server_default="COORDINATOR", nullable=False),
        sa.Column("administrator_id", sa.BigInteger(), nullable=False),
        sa.Column("check_in_qr_code", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["category_id"], ["resource_categories.id"]),
        sa.ForeignKeyConstraint(["administrator_id"], ["users.id"]),
        sa.UniqueConstraint("check_in_qr_code"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'MAINTENANCE', 'FAULTY')", name="resources_status_check"
        ),
        sa.CheckConstraint(
            "approval_flow IN ('AUTO', 'COORDINATOR', 'COORDINATOR_AND_ADMIN')",
            name="resources_approval_flow_check",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(specifications) = 'object'", name="resources_specs_object_ck"
        ),
    )
    op.create_index(
        "resources_category_idx",
        "resources",
        ["category_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "resources_admin_idx",
        "resources",
        ["administrator_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("resources_tags_gin", "resources", ["tags"], postgresql_using="gin")

    op.create_table(
        "usage_rules",
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "min_duration_minutes", sa.Integer(), server_default=sa.text("30"), nullable=False
        ),
        sa.Column(
            "max_duration_minutes", sa.Integer(), server_default=sa.text("240"), nullable=False
        ),
        sa.Column(
            "break_between_minutes", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "check_in_deadline_minutes",
            sa.Integer(),
            server_default=sa.text("15"),
            nullable=False,
        ),
        sa.Column("required_certification_level", sa.SmallInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("resource_id"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.CheckConstraint(
            "min_duration_minutes >= 0", name="usage_rules_min_duration_minutes_check"
        ),
        sa.CheckConstraint(
            "max_duration_minutes >= 1", name="usage_rules_max_duration_minutes_check"
        ),
        sa.CheckConstraint(
            "break_between_minutes >= 0", name="usage_rules_break_between_minutes_check"
        ),
        sa.CheckConstraint(
            "check_in_deadline_minutes BETWEEN 15 AND 30",
            name="usage_rules_check_in_deadline_minutes_check",
        ),
        sa.CheckConstraint(
            "required_certification_level BETWEEN 1 AND 5",
            name="usage_rules_required_certification_level_check",
        ),
        sa.CheckConstraint(
            "min_duration_minutes <= max_duration_minutes", name="usage_rules_duration_ck"
        ),
    )

    op.create_table(
        "resource_files",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.UniqueConstraint("storage_key"),
        sa.CheckConstraint("type IN ('MANUAL', 'PHOTO')", name="resource_files_type_check"),
        sa.CheckConstraint(
            "size_bytes BETWEEN 0 AND 20971520", name="resource_files_size_bytes_check"
        ),
    )
    op.create_index("resource_files_resource_idx", "resource_files", ["resource_id"])

    op.create_table(
        "certifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("granted_by", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"]),
        sa.CheckConstraint("level BETWEEN 1 AND 5", name="certifications_level_check"),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoke_reason IS NULL)"
            " AND (revoked_at IS NULL) = (revoked_by IS NULL)",
            name="certifications_revoke_ck",
        ),
    )
    # Cel mult o certificare nerevocată per (utilizator, resursă).
    op.create_index(
        "certifications_one_open_uq",
        "certifications",
        ["user_id", "resource_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("certifications_resource_idx", "certifications", ["resource_id"])


def _create_maintenance_and_reservations() -> None:
    """Blocările de mentenanță, rezervările și aprobările."""
    op.create_table(
        "maintenance_blocks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("work_type", sa.Text(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.Text(), server_default="SCHEDULED", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.CheckConstraint(
            "work_type IN ('MAINTENANCE', 'CALIBRATION')",
            name="maintenance_blocks_work_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'ACTIVE', 'ENDED', 'CANCELLED')",
            name="maintenance_blocks_status_check",
        ),
        sa.CheckConstraint("end_at IS NULL OR end_at > start_at", name="maintenance_interval_ck"),
        sa.CheckConstraint(
            "(status = 'ENDED') = (ended_at IS NOT NULL)"
            " AND (status = 'CANCELLED') = (cancelled_at IS NOT NULL)",
            name="maintenance_status_dates_ck",
        ),
        postgresql.ExcludeConstraint(
            (sa.column("resource_id"), "="),
            (sa.text("tstzrange(start_at, end_at, '[)')"), "&&"),
            where=sa.text("status IN ('SCHEDULED', 'ACTIVE')"),
            using="gist",
            name="maintenance_no_overlap",
        ),
    )
    op.create_index(
        "maintenance_blocks_resource_idx",
        "maintenance_blocks",
        ["resource_id", sa.literal_column("start_at DESC")],
    )

    op.create_table(
        "reservations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("requester_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "hours",
            sa.Numeric(precision=8, scale=2),
            sa.Computed(
                "round((extract(epoch FROM (end_at - start_at)) / 3600)::numeric, 2)",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("purpose", sa.String(length=500), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("approval_flow", sa.Text(), nullable=False),
        sa.Column("check_in_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_in_method", sa.Text(), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.BigInteger(), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("maintenance_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["maintenance_id"], ["maintenance_blocks.id"]),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS',"
            " 'COMPLETED', 'REJECTED', 'CANCELLED', 'AUTO_CANCELLED')",
            name="reservations_status_check",
        ),
        sa.CheckConstraint(
            "approval_flow IN ('AUTO', 'COORDINATOR', 'COORDINATOR_AND_ADMIN')",
            name="reservations_approval_flow_check",
        ),
        sa.CheckConstraint(
            "check_in_method IN ('WEB', 'QR')", name="reservations_check_in_method_check"
        ),
        sa.CheckConstraint("end_at > start_at", name="reservations_interval_ck"),
        sa.CheckConstraint(
            "check_in_deadline > start_at AND check_in_deadline <= end_at",
            name="reservations_deadline_ck",
        ),
        sa.CheckConstraint(
            "(check_in_at IS NULL) = (check_in_method IS NULL)", name="reservations_check_in_ck"
        ),
        sa.CheckConstraint(
            "(status IN ('CANCELLED', 'AUTO_CANCELLED')) = (cancelled_at IS NOT NULL)",
            name="reservations_cancel_ck",
        ),
        postgresql.ExcludeConstraint(
            (sa.column("resource_id"), "="),
            (sa.text("tstzrange(start_at, end_at, '[)')"), "&&"),
            where=sa.text("status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS')"),
            using="gist",
            name="reservations_no_overlap",
        ),
    )
    op.create_index(
        "reservations_requester_idx",
        "reservations",
        ["requester_id", sa.literal_column("start_at DESC")],
    )
    op.create_index("reservations_project_idx", "reservations", ["project_id"])
    op.create_index("reservations_resource_time_idx", "reservations", ["resource_id", "start_at"])
    op.create_index(
        "reservations_pending_idx",
        "reservations",
        ["status"],
        postgresql_where=sa.text("status IN ('PENDING', 'PENDING_ADMIN')"),
    )
    op.create_index(
        "reservations_check_in_due_idx",
        "reservations",
        ["check_in_deadline"],
        postgresql_where=sa.text("status = 'CONFIRMED'"),
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("reservation_id", sa.BigInteger(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("approver_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.CheckConstraint(
            "stage IN ('COORDINATOR', 'RESOURCE_ADMIN')", name="approvals_stage_check"
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED')", name="approvals_decision_check"
        ),
        sa.UniqueConstraint("reservation_id", "stage", name="approvals_reservation_id_stage_key"),
        sa.CheckConstraint(
            "decision = 'APPROVED' OR comment IS NOT NULL", name="approvals_reject_reason_ck"
        ),
    )


def _create_notifications_and_settings() -> None:
    """Notificările (e-mail și în aplicație) și setările globale."""
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reservation_id", sa.BigInteger(), nullable=True),
        sa.Column("maintenance_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("send_attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["maintenance_id"], ["maintenance_blocks.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint("channel IN ('EMAIL', 'IN_APP')", name="notifications_channel_check"),
    )
    op.create_index(
        "notifications_inbox_idx",
        "notifications",
        ["recipient_id", sa.literal_column("created_at DESC")],
        postgresql_where=sa.text("channel = 'IN_APP'"),
    )
    op.create_index(
        "notifications_outbox_idx",
        "notifications",
        ["created_at"],
        postgresql_where=sa.text("channel = 'EMAIL' AND sent_at IS NULL"),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
    )
