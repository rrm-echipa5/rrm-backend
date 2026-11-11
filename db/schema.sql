-- =============================================================================
-- Research Resource Manager - schema bazei de date (PostgreSQL 16+ / 18)
-- Laboratorul 5, 9.6 / 9.7 - Andronache Daniele (KAN-55, KAN-56)
--
-- Pornește de la diagramele de clase (domeniu) 8.1 - 8.3 din Documentul de Arhitectură
-- și de la contractul API rrm-api.yaml. Denumirile sunt în engleză, ca în API
-- (tabele la plural, coloane snake_case); enumerările din API sunt coloane text cu CHECK,
-- cu aceleași valori (mai ușor de modificat prin migrări Alembic decât tipurile ENUM).
--
-- Rulare: psql -d rrm -f schema.sql   (apoi, opțional, seed.sql)
-- =============================================================================

BEGIN;

-- Constrângerile de excludere (fără suprapuneri de intervale pe aceeași resursă)
-- combină egalitatea pe resource_id cu suprapunerea de intervale, deci au nevoie de btree_gist.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- -----------------------------------------------------------------------------
-- Utilizatori, autentificare
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name               varchar(150) NOT NULL,
    email              varchar(254) NOT NULL,
    password_hash      varchar(255) NOT NULL,                 -- Argon2 (pwdlib)
    role               text NOT NULL
                       CHECK (role IN ('STUDENT', 'RESEARCHER', 'RESOURCE_ADMIN', 'SYSTEM_ADMIN')),
    two_factor_enabled boolean NOT NULL DEFAULT false,
    totp_secret        varchar(64),                            -- secretul TOTP (pyotp), criptat de aplicație
    is_active          boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_totp_ck CHECK (NOT two_factor_enabled OR totp_secret IS NOT NULL)
);
CREATE UNIQUE INDEX users_email_uq ON users (lower(email));

-- Pasul 2 al autentificării: challengeId primit la POST /auth/login, valabil 5 minute.
CREATE TABLE two_factor_challenges (
    id          uuid PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    attempts    smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    expires_at  timestamptz NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX two_factor_challenges_user_idx ON two_factor_challenges (user_id);

-- Dispozitive memorate 5 zile (rememberDevice: true).
CREATE TABLE trusted_devices (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash  varchar(128) NOT NULL UNIQUE,
    expires_at  timestamptz NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX trusted_devices_user_idx ON trusted_devices (user_id);

-- Token-uri de reînnoire (POST /auth/refresh, POST /auth/logout).
CREATE TABLE refresh_tokens (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash  varchar(128) NOT NULL UNIQUE,
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);

-- -----------------------------------------------------------------------------
-- Echipe și proiecte cu buget de ore
-- -----------------------------------------------------------------------------
CREATE TABLE teams (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            varchar(150) NOT NULL UNIQUE,
    coordinator_id  bigint NOT NULL REFERENCES users (id),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX teams_coordinator_idx ON teams (coordinator_id);

-- Un utilizator poate fi membru în mai multe echipe (asocierea M:N din diagrama 8.3).
CREATE TABLE team_members (
    team_id    bigint NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    user_id    bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    joined_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);
CREATE INDEX team_members_user_idx ON team_members (user_id);

CREATE TABLE projects (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id       bigint NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    title         varchar(200) NOT NULL,
    budget_hours  numeric(8, 2) NOT NULL CHECK (budget_hours >= 0),
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (team_id, title)
);

-- -----------------------------------------------------------------------------
-- Resurse, reguli, fișiere, certificări
-- -----------------------------------------------------------------------------
CREATE TABLE resource_categories (
    id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code  text NOT NULL UNIQUE
          CHECK (code IN ('HARDWARE', 'HPC', 'ROOM', 'MEASUREMENT_INSTRUMENT')),
    name  varchar(100) NOT NULL
);

CREATE TABLE resources (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name              varchar(150) NOT NULL,
    category_id       bigint NOT NULL REFERENCES resource_categories (id),
    location          varchar(200),
    description       text,
    specifications    jsonb NOT NULL DEFAULT '{}'::jsonb,     -- perechi denumire - valoare
    tags              text[] NOT NULL DEFAULT '{}',
    status            text NOT NULL DEFAULT 'ACTIVE'
                      CHECK (status IN ('ACTIVE', 'MAINTENANCE', 'FAULTY')),
    approval_flow     text NOT NULL DEFAULT 'COORDINATOR'
                      CHECK (approval_flow IN ('AUTO', 'COORDINATOR', 'COORDINATOR_AND_ADMIN')),
    administrator_id  bigint NOT NULL REFERENCES users (id),
    check_in_qr_code  varchar(64) NOT NULL UNIQUE,            -- conținutul codului QR de pe resursă
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    deleted_at        timestamptz,                            -- ștergere logică (DELETE /resources/{id})
    CONSTRAINT resources_specs_object_ck CHECK (jsonb_typeof(specifications) = 'object')
);
CREATE INDEX resources_category_idx ON resources (category_id) WHERE deleted_at IS NULL;
CREATE INDEX resources_admin_idx ON resources (administrator_id) WHERE deleted_at IS NULL;
CREATE INDEX resources_tags_gin ON resources USING gin (tags);

-- Regula de utilizare (1:1 cu resursa).
CREATE TABLE usage_rules (
    resource_id                  bigint PRIMARY KEY REFERENCES resources (id) ON DELETE CASCADE,
    min_duration_minutes         integer NOT NULL DEFAULT 30  CHECK (min_duration_minutes >= 0),
    max_duration_minutes         integer NOT NULL DEFAULT 240 CHECK (max_duration_minutes >= 1),
    break_between_minutes        integer NOT NULL DEFAULT 0   CHECK (break_between_minutes >= 0),
    check_in_deadline_minutes    integer NOT NULL DEFAULT 15  CHECK (check_in_deadline_minutes BETWEEN 15 AND 30),
    required_certification_level smallint CHECK (required_certification_level BETWEEN 1 AND 5),
    updated_at                   timestamptz NOT NULL DEFAULT now(),
    updated_by                   bigint REFERENCES users (id),
    CONSTRAINT usage_rules_duration_ck CHECK (min_duration_minutes <= max_duration_minutes)
);

-- Manuale PDF și poze (conținutul este în stocarea de fișiere, aici doar metadatele).
CREATE TABLE resource_files (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id   bigint NOT NULL REFERENCES resources (id) ON DELETE CASCADE,
    type          text NOT NULL CHECK (type IN ('MANUAL', 'PHOTO')),
    title         varchar(200) NOT NULL,
    file_name     varchar(255) NOT NULL,
    content_type  varchar(100) NOT NULL,
    size_bytes    bigint NOT NULL CHECK (size_bytes BETWEEN 0 AND 20971520),   -- maxim 20 MB
    storage_key   varchar(500) NOT NULL UNIQUE,
    uploaded_by   bigint NOT NULL REFERENCES users (id),
    uploaded_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX resource_files_resource_idx ON resource_files (resource_id);

-- Certificarea unui utilizator pentru o resursă. Starea din API se calculează:
-- REVOKED dacă revoked_at e completat, EXPIRED dacă expires_at < azi, altfel ACTIVE.
CREATE TABLE certifications (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    resource_id    bigint NOT NULL REFERENCES resources (id) ON DELETE CASCADE,
    level          smallint NOT NULL CHECK (level BETWEEN 1 AND 5),
    granted_at     timestamptz NOT NULL DEFAULT now(),
    granted_by     bigint NOT NULL REFERENCES users (id),
    expires_at     date,
    revoked_at     timestamptz,
    revoked_by     bigint REFERENCES users (id),
    revoke_reason  varchar(500),
    CONSTRAINT certifications_revoke_ck
        CHECK ((revoked_at IS NULL) = (revoke_reason IS NULL) AND (revoked_at IS NULL) = (revoked_by IS NULL))
);
-- Cel mult o certificare nerevocată per (utilizator, resursă) -> 409 CERTIFICATION_EXISTS.
CREATE UNIQUE INDEX certifications_one_open_uq ON certifications (user_id, resource_id) WHERE revoked_at IS NULL;
CREATE INDEX certifications_resource_idx ON certifications (resource_id);

-- -----------------------------------------------------------------------------
-- Mentenanță (cazul de utilizare 2.3)
-- -----------------------------------------------------------------------------
CREATE TABLE maintenance_blocks (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id   bigint NOT NULL REFERENCES resources (id) ON DELETE CASCADE,
    work_type     text NOT NULL CHECK (work_type IN ('MAINTENANCE', 'CALIBRATION')),
    start_at      timestamptz NOT NULL,
    end_at        timestamptz,                                -- NULL = durată nedeterminată
    reason        varchar(500) NOT NULL,
    status        text NOT NULL DEFAULT 'SCHEDULED'
                  CHECK (status IN ('SCHEDULED', 'ACTIVE', 'ENDED', 'CANCELLED')),
    created_by    bigint NOT NULL REFERENCES users (id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    ended_at      timestamptz,
    cancelled_at  timestamptz,
    CONSTRAINT maintenance_interval_ck CHECK (end_at IS NULL OR end_at > start_at),
    CONSTRAINT maintenance_status_dates_ck CHECK (
        (status = 'ENDED') = (ended_at IS NOT NULL) AND (status = 'CANCELLED') = (cancelled_at IS NOT NULL)),
    -- Două blocări programate sau în curs nu se pot suprapune pe aceeași resursă (409 MAINTENANCE_OVERLAP).
    CONSTRAINT maintenance_no_overlap EXCLUDE USING gist (
        resource_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status IN ('SCHEDULED', 'ACTIVE'))
);
CREATE INDEX maintenance_blocks_resource_idx ON maintenance_blocks (resource_id, start_at DESC);

-- -----------------------------------------------------------------------------
-- Rezervări și aprobări (cazurile de utilizare 2.1 și 2.2)
-- -----------------------------------------------------------------------------
CREATE TABLE reservations (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id       bigint NOT NULL REFERENCES resources (id),
    requester_id      bigint NOT NULL REFERENCES users (id),
    project_id        bigint NOT NULL REFERENCES projects (id),
    start_at          timestamptz NOT NULL,
    end_at            timestamptz NOT NULL,
    hours             numeric(8, 2) GENERATED ALWAYS AS (
                          round((extract(epoch FROM (end_at - start_at)) / 3600)::numeric, 2)) STORED,
    purpose           varchar(500) NOT NULL,
    status            text NOT NULL
                      CHECK (status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS',
                                        'COMPLETED', 'REJECTED', 'CANCELLED', 'AUTO_CANCELLED')),
    approval_flow     text NOT NULL                           -- fluxul resursei la momentul cererii
                      CHECK (approval_flow IN ('AUTO', 'COORDINATOR', 'COORDINATOR_AND_ADMIN')),
    check_in_deadline timestamptz NOT NULL,                   -- start_at + termenul de check-in din reguli
    check_in_at       timestamptz,
    check_in_method   text CHECK (check_in_method IN ('WEB', 'QR')),
    check_out_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    cancelled_at      timestamptz,
    cancelled_by      bigint REFERENCES users (id),           -- NULL la anularea automată
    cancel_reason     varchar(500),
    maintenance_id    bigint REFERENCES maintenance_blocks (id), -- blocarea care a anulat rezervarea
    CONSTRAINT reservations_interval_ck CHECK (end_at > start_at),
    CONSTRAINT reservations_deadline_ck CHECK (check_in_deadline > start_at AND check_in_deadline <= end_at),
    CONSTRAINT reservations_check_in_ck CHECK ((check_in_at IS NULL) = (check_in_method IS NULL)),
    CONSTRAINT reservations_cancel_ck CHECK (
        (status IN ('CANCELLED', 'AUTO_CANCELLED')) = (cancelled_at IS NOT NULL)),
    -- Intervalul unei cereri active blochează resursa: nicio altă cerere activă nu se poate suprapune
    -- (409 SLOT_UNAVAILABLE). Pauza dintre rezervări se verifică în Reservations Service.
    CONSTRAINT reservations_no_overlap EXCLUDE USING gist (
        resource_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status IN ('PENDING', 'PENDING_ADMIN', 'CONFIRMED', 'IN_PROGRESS'))
);
CREATE INDEX reservations_requester_idx ON reservations (requester_id, start_at DESC);
CREATE INDEX reservations_project_idx ON reservations (project_id);
CREATE INDEX reservations_resource_time_idx ON reservations (resource_id, start_at);
CREATE INDEX reservations_pending_idx ON reservations (status) WHERE status IN ('PENDING', 'PENDING_ADMIN');
CREATE INDEX reservations_check_in_due_idx ON reservations (check_in_deadline) WHERE status = 'CONFIRMED';

-- 0, 1 sau 2 decizii per rezervare, câte una pe etapă.
CREATE TABLE approvals (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reservation_id  bigint NOT NULL REFERENCES reservations (id) ON DELETE CASCADE,
    stage           text NOT NULL CHECK (stage IN ('COORDINATOR', 'RESOURCE_ADMIN')),
    decision        text NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
    approver_id     bigint NOT NULL REFERENCES users (id),
    decided_at      timestamptz NOT NULL DEFAULT now(),
    comment         varchar(500),
    UNIQUE (reservation_id, stage),
    CONSTRAINT approvals_reject_reason_ck CHECK (decision = 'APPROVED' OR comment IS NOT NULL)
);

-- -----------------------------------------------------------------------------
-- Notificări (e-mail și in-app) și setări globale
-- -----------------------------------------------------------------------------
CREATE TABLE notifications (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipient_id    bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    channel         text NOT NULL CHECK (channel IN ('EMAIL', 'IN_APP')),
    type            varchar(50) NOT NULL,                     -- ex. RESERVATION_CANCELLED_MAINTENANCE
    title           varchar(200) NOT NULL,
    body            text NOT NULL,
    reservation_id  bigint REFERENCES reservations (id) ON DELETE SET NULL,
    maintenance_id  bigint REFERENCES maintenance_blocks (id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    read_at         timestamptz,                              -- doar IN_APP
    sent_at         timestamptz,                              -- doar EMAIL; NULL = de trimis
    send_attempts   smallint NOT NULL DEFAULT 0,
    last_error      varchar(500)
);
CREATE INDEX notifications_inbox_idx ON notifications (recipient_id, created_at DESC) WHERE channel = 'IN_APP';
CREATE INDEX notifications_outbox_idx ON notifications (created_at) WHERE channel = 'EMAIL' AND sent_at IS NULL;

CREATE TABLE app_settings (
    key         varchar(100) PRIMARY KEY,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  bigint REFERENCES users (id)
);

-- -----------------------------------------------------------------------------
-- Vederi folosite de API
-- -----------------------------------------------------------------------------
-- Bugetul de ore al proiectelor (ProjectBudget în API): orele consumate sunt ale rezervărilor
-- confirmate, în desfășurare sau finalizate; nu se păstrează separat, ca să nu se desincronizeze.
CREATE VIEW project_budgets AS
SELECT p.id,
       p.team_id,
       p.title,
       p.budget_hours,
       coalesce(sum(r.hours) FILTER (WHERE r.status IN ('CONFIRMED', 'IN_PROGRESS', 'COMPLETED')), 0)
           AS used_hours,
       p.budget_hours
           - coalesce(sum(r.hours) FILTER (WHERE r.status IN ('CONFIRMED', 'IN_PROGRESS', 'COMPLETED')), 0)
           AS remaining_hours
FROM projects p
LEFT JOIN reservations r ON r.project_id = p.id
GROUP BY p.id;

-- Starea certificărilor, cum apare în API (CertificationStatus).
CREATE VIEW certification_statuses AS
SELECT c.*,
       CASE WHEN c.revoked_at IS NOT NULL THEN 'REVOKED'
            WHEN c.expires_at IS NOT NULL AND c.expires_at < current_date THEN 'EXPIRED'
            ELSE 'ACTIVE' END AS status
FROM certifications c;

COMMIT;
