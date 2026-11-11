-- =============================================================================
-- Research Resource Manager - date de test (Laboratorul 5, 9.7, KAN-56)
-- Andronache Daniele
--
-- Datele sunt aceleași ca în prototipurile Figma și în exemplele din rrm-api.yaml
-- (Microscop electronic SEM = resursa 7, rezervarea 1042, Ana Popescu etc.).
-- Toate conturile de test au aceeași parolă, Test-RRM-2026! (hash Argon2id).
-- Doar pentru dezvoltare locală; nu se rulează pe un server real.
--
-- Rulare: psql -d rrm -f schema.sql -f seed.sql
-- =============================================================================

BEGIN;

-- Utilizatori ------------------------------------------------------------------
INSERT INTO users (id, name, email, password_hash, role, two_factor_enabled, totp_secret)
OVERRIDING SYSTEM VALUE VALUES
 (1, 'Elena Marin',    'elena.marin@usv.ro',             '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'SYSTEM_ADMIN',   true,  'JBSWY3DPEHPK3PXP'),
 (2, 'Andrei Rusu',    'andrei.rusu@usv.ro',             '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'RESEARCHER',     true,  'KRSXG5CTMVRXEZLU'),
 (3, 'Ana Popescu',    'ana.popescu@student.usv.ro',     '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'STUDENT',        true,  'MFRGGZDFMZTWQ2LK'),
 (4, 'Mihai Ionescu',  'mihai.ionescu@usv.ro',           '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'RESOURCE_ADMIN', false, NULL),
 (5, 'Ioana Dumitru',  'ioana.dumitru@student.usv.ro',   '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'STUDENT',        false, NULL),
 (6, 'Radu Stan',      'radu.stan@usv.ro',               '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'RESEARCHER',     false, NULL),
 (7, 'Vlad Popa',      'vlad.popa@usv.ro',               '$argon2id$v=19$m=65536,t=3,p=4$i0XS+bR5ZSiPq9csSsuC4A$mzvQVTuWOn8cFrBBUqhQO/T13YE7B2pl2bTybBBHeRE', 'RESOURCE_ADMIN', false, NULL);

-- Echipe, membri, proiecte ---------------------------------------------------------
INSERT INTO teams (id, name, coordinator_id) OVERRIDING SYSTEM VALUE VALUES
 (1, 'Laboratorul de Nanomateriale', 2),
 (2, 'Grupul de Calcul Științific',  6);

INSERT INTO team_members (team_id, user_id) VALUES
 (1, 2), (1, 3), (1, 5),
 (2, 6), (2, 5);

INSERT INTO projects (id, team_id, title, budget_hours) OVERRIDING SYSTEM VALUE VALUES
 (1, 1, 'Nanostructuri pentru senzori de gaz', 120),
 (2, 1, 'Filme subțiri de ZnO',                 60),
 (3, 2, 'Simulări de dinamică moleculară',     200);

-- Categorii și resurse --------------------------------------------------------------
INSERT INTO resource_categories (id, code, name) OVERRIDING SYSTEM VALUE VALUES
 (1, 'HARDWARE',               'Echipamente hardware'),
 (2, 'HPC',                    'Calcul de înaltă performanță'),
 (3, 'ROOM',                   'Săli și spații'),
 (4, 'MEASUREMENT_INSTRUMENT', 'Instrumente de măsură');

INSERT INTO resources (id, name, category_id, location, description, specifications, tags,
                       approval_flow, administrator_id, check_in_qr_code) OVERRIDING SYSTEM VALUE VALUES
 (7,  'Microscop electronic SEM', 1, 'Corp C, sala C204',
      'Microscop electronic cu baleiaj, cu detector EDS pentru analiză elementală.',
      '{"Rezoluție": "1,2 nm la 30 kV", "Detector": "EDS Oxford Ultim Max 65"}',
      '{microscopie,imagistică}', 'COORDINATOR_AND_ADMIN', 4, 'RRM-R7-6f1c2a'),
 (9,  'Microscop electronic TEM', 1, 'Corp C, sala C206',
      'Microscop electronic prin transmisie, 200 kV.',
      '{"Tensiune": "200 kV", "Rezoluție": "0,19 nm"}',
      '{microscopie,imagistică}', 'COORDINATOR_AND_ADMIN', 4, 'RRM-R9-b37e90'),
 (10, 'Cluster HPC - nod GPU', 2, 'Centrul de date USV',
      'Nod de calcul cu 4 GPU-uri pentru simulări și antrenarea modelelor.',
      '{"GPU": "4 x NVIDIA L40S", "RAM": "512 GB"}',
      '{hpc,gpu,simulare}', 'AUTO', 7, 'RRM-R10-0a4d55'),
 (11, 'Sala de seminar C105', 3, 'Corp C, sala C105',
      'Sală pentru 30 de persoane, cu videoproiector.',
      '{"Capacitate": "30 de locuri"}',
      '{sală,prezentări}', 'AUTO', 7, 'RRM-R11-91c7e2'),
 (12, 'Spectrometru Raman', 4, 'Corp C, sala C210',
      'Spectrometru Raman confocal, lasere de 532 nm și 785 nm.',
      '{"Lasere": "532 nm, 785 nm"}',
      '{spectroscopie}', 'COORDINATOR', 4, 'RRM-R12-c45b18');

INSERT INTO usage_rules (resource_id, min_duration_minutes, max_duration_minutes, break_between_minutes,
                         check_in_deadline_minutes, required_certification_level, updated_by) VALUES
 (7,  30, 240, 15, 15, 2,    4),
 (9,  60, 240, 30, 15, 3,    4),
 (10, 60, 720,  0, 30, NULL, 7),
 (11, 30, 180,  0, 15, NULL, 7),
 (12, 30, 120, 10, 15, 1,    4);

INSERT INTO resource_files (resource_id, type, title, file_name, content_type, size_bytes, storage_key, uploaded_by) VALUES
 (7,  'MANUAL', 'Manual de utilizare SEM',    'manual-sem.pdf',   'application/pdf', 2483120, 'resources/7/manual-sem.pdf',   4),
 (7,  'PHOTO',  'Microscopul SEM',            'sem.jpg',          'image/jpeg',       412883, 'resources/7/sem.jpg',          4),
 (12, 'MANUAL', 'Procedura de lucru Raman',   'raman.pdf',        'application/pdf',   918204, 'resources/12/raman.pdf',      4);

-- Certificări (una retrasă, ca exemplu pentru revoke) --------------------------------
INSERT INTO certifications (user_id, resource_id, level, granted_at, granted_by, expires_at,
                            revoked_at, revoked_by, revoke_reason) VALUES
 (3, 7,  2, '2026-10-01 10:00+03', 4, '2027-10-31', NULL, NULL, NULL),
 (3, 12, 1, '2026-10-01 10:30+03', 4, '2027-10-31', NULL, NULL, NULL),
 (5, 7,  1, '2026-10-15 12:00+03', 4, '2027-10-31', NULL, NULL, NULL),
 (5, 9,  1, '2026-10-15 12:30+03', 4, NULL,
      '2026-11-02 09:00+02', 4, 'Nu a respectat procedura de oprire a fasciculului.'),
 (2, 7,  3, '2026-09-20 09:00+03', 4, NULL, NULL, NULL, NULL);

-- Blocări pentru mentenanță ---------------------------------------------------------------
INSERT INTO maintenance_blocks (id, resource_id, work_type, start_at, end_at, reason, status,
                                created_by, created_at, ended_at) OVERRIDING SYSTEM VALUE VALUES
 (30, 7, 'MAINTENANCE', '2026-11-03 08:00+02', '2026-11-03 17:00+02',
      'Înlocuirea filamentului.', 'ENDED', 4, '2026-11-01 14:00+02', '2026-11-03 17:00+02'),
 (31, 7, 'CALIBRATION', '2026-11-20 08:00+02', '2026-11-21 18:00+02',
      'Calibrarea anuală a detectorului EDS.', 'SCHEDULED', 4, '2026-11-08 21:30+02', NULL);

-- Rezervări, în toate statusurile din diagrama de stări ---------------------------------
INSERT INTO reservations (id, resource_id, requester_id, project_id, start_at, end_at, purpose, status,
                          approval_flow, check_in_deadline, check_in_at, check_in_method, check_out_at,
                          created_at, cancelled_at, cancelled_by, cancel_reason, maintenance_id)
OVERRIDING SYSTEM VALUE VALUES
 -- anulată din cauza mentenanței 30 (rezervarea SEM din 3 noiembrie din prototipul 9.3)
 (1040, 7, 3, 1, '2026-11-03 10:00+02', '2026-11-03 12:00+02', 'Imagini SEM pentru probele de ZnO.',
        'CANCELLED', 'COORDINATOR_AND_ADMIN', '2026-11-03 10:15+02', NULL, NULL, NULL,
        '2026-10-28 11:00+02', '2026-11-01 14:00+02', 4, 'Mentenanță: Înlocuirea filamentului.', 30),
 -- finalizată, cu check-in prin QR
 (1041, 12, 3, 1, '2026-11-05 09:00+02', '2026-11-05 11:00+02', 'Spectre Raman pentru probele S1-S4.',
        'COMPLETED', 'COORDINATOR', '2026-11-05 09:15+02', '2026-11-05 09:04+02', 'QR', '2026-11-05 10:52+02',
        '2026-11-02 16:20+02', NULL, NULL, NULL, NULL),
 -- aprobată de coordonator, așteaptă avizul administratorului (exemplul 1042 din API)
 (1042, 7, 3, 1, '2026-11-12 10:00+02', '2026-11-12 12:00+02', 'Imagini SEM pentru probele de ZnO depuse în octombrie.',
        'PENDING_ADMIN', 'COORDINATOR_AND_ADMIN', '2026-11-12 10:15+02', NULL, NULL, NULL,
        '2026-11-06 18:40+02', NULL, NULL, NULL, NULL),
 -- confirmată automat (resursă AUTO)
 (1043, 10, 5, 3, '2026-11-10 08:00+02', '2026-11-10 20:00+02', 'Simulare MD, 2 milioane de atomi.',
        'CONFIRMED', 'AUTO', '2026-11-10 08:30+02', NULL, NULL, NULL,
        '2026-11-07 09:10+02', NULL, NULL, NULL, NULL),
 -- confirmată, apoi anulată la programarea calibrării 31
 (1044, 7, 3, 2, '2026-11-20 13:00+02', '2026-11-20 15:00+02', 'Morfologia filmelor de ZnO.',
        'CANCELLED', 'COORDINATOR_AND_ADMIN', '2026-11-20 13:15+02', NULL, NULL, NULL,
        '2026-11-04 12:00+02', '2026-11-08 21:30+02', 4, 'Mentenanță: Calibrarea anuală a detectorului EDS.', 31),
 -- respinsă de coordonator
 (1045, 9, 5, 2, '2026-11-14 14:00+02', '2026-11-14 16:00+02', 'Difracție de electroni pe filme ZnO.',
        'REJECTED', 'COORDINATOR_AND_ADMIN', '2026-11-14 14:15+02', NULL, NULL, NULL,
        '2026-11-06 10:00+02', NULL, NULL, NULL, NULL),
 -- rezervare directă a coordonatorului
 (1046, 7, 2, 1, '2026-11-13 09:00+02', '2026-11-13 11:00+02', 'Verificarea probelor înainte de publicare.',
        'CONFIRMED', 'COORDINATOR_AND_ADMIN', '2026-11-13 09:15+02', NULL, NULL, NULL,
        '2026-11-07 15:30+02', NULL, NULL, NULL, NULL),
 -- anulată automat, fără check-in
 (1047, 11, 3, 1, '2026-11-06 12:00+02', '2026-11-06 13:00+02', 'Repetiție pentru prezentarea de grup.',
        'AUTO_CANCELLED', 'AUTO', '2026-11-06 12:15+02', NULL, NULL, NULL,
        '2026-11-05 20:00+02', '2026-11-06 12:15+02', NULL, 'Fără check-in în termen.', NULL),
 -- cerere nouă, în așteptarea coordonatorului
 (1048, 12, 5, 2, '2026-11-11 14:00+02', '2026-11-11 15:30+02', 'Spectre Raman de control.',
        'PENDING', 'COORDINATOR', '2026-11-11 14:15+02', NULL, NULL, NULL,
        '2026-11-08 19:45+02', NULL, NULL, NULL, NULL);

INSERT INTO approvals (reservation_id, stage, decision, approver_id, decided_at, comment) VALUES
 (1040, 'COORDINATOR',    'APPROVED', 2, '2026-10-28 14:00+02', NULL),
 (1040, 'RESOURCE_ADMIN', 'APPROVED', 4, '2026-10-29 09:00+02', NULL),
 (1041, 'COORDINATOR',    'APPROVED', 2, '2026-11-03 08:30+02', NULL),
 (1042, 'COORDINATOR',    'APPROVED', 2, '2026-11-07 10:00+02', NULL),
 (1044, 'COORDINATOR',    'APPROVED', 2, '2026-11-04 15:00+02', NULL),
 (1044, 'RESOURCE_ADMIN', 'APPROVED', 4, '2026-11-05 09:30+02', NULL),
 (1045, 'COORDINATOR',    'REJECTED', 2, '2026-11-06 16:00+02', 'Certificarea pentru TEM a fost retrasă; reprogramează după recertificare.');

-- Notificări ----------------------------------------------------------------------------
INSERT INTO notifications (recipient_id, channel, type, title, body, reservation_id, maintenance_id,
                           created_at, read_at, sent_at) VALUES
 (3, 'IN_APP', 'RESERVATION_CANCELLED_MAINTENANCE', 'Rezervare anulată: Microscop electronic SEM',
     'Rezervarea din 20.11.2026, 13:00-15:00 a fost anulată: Calibrarea anuală a detectorului EDS. Sloturi libere: 22.11.2026, 13:00-15:00.',
     1044, 31, '2026-11-08 21:30+02', NULL, NULL),
 (3, 'EMAIL',  'RESERVATION_CANCELLED_MAINTENANCE', 'Rezervare anulată: Microscop electronic SEM',
     'Rezervarea din 20.11.2026, 13:00-15:00 a fost anulată: Calibrarea anuală a detectorului EDS.',
     1044, 31, '2026-11-08 21:30+02', NULL, NULL),
 (2, 'IN_APP', 'RESERVATION_CANCELLED_MAINTENANCE', 'Rezervare anulată în echipa ta',
     'Rezervarea Anei Popescu pentru Microscop electronic SEM (20.11.2026) a fost anulată din cauza unei calibrări.',
     1044, 31, '2026-11-08 21:30+02', NULL, NULL),
 (4, 'IN_APP', 'APPROVAL_REQUIRED', 'Aviz necesar: Microscop electronic SEM',
     'Cererea Anei Popescu din 12.11.2026, 10:00-12:00 așteaptă avizul tău.',
     1042, NULL, '2026-11-07 10:00+02', NULL, NULL),
 (2, 'IN_APP', 'APPROVAL_REQUIRED', 'Cerere nouă: Spectrometru Raman',
     'Ioana Dumitru a cerut Spectrometru Raman pe 11.11.2026, 14:00-15:30.',
     1048, NULL, '2026-11-08 19:45+02', NULL, NULL);

-- Setări globale -----------------------------------------------------------------------------
INSERT INTO app_settings (key, value, updated_by) VALUES
 ('reminders.hoursBefore',            '[24, 1]', 1),
 ('auth.trustedDeviceDays',           '5', 1),
 ('auth.accessTokenMinutes',          '15', 1),
 ('calendar.maxRangeDays',            '31', 1),
 ('notifications.emailRetryMinutes',  '[5, 15, 60]', 1);

-- Contoarele de identitate continuă după id-urile fixe de mai sus.
SELECT setval(pg_get_serial_sequence('users', 'id'),               (SELECT max(id) FROM users));
SELECT setval(pg_get_serial_sequence('teams', 'id'),               (SELECT max(id) FROM teams));
SELECT setval(pg_get_serial_sequence('projects', 'id'),            (SELECT max(id) FROM projects));
SELECT setval(pg_get_serial_sequence('resource_categories', 'id'), (SELECT max(id) FROM resource_categories));
SELECT setval(pg_get_serial_sequence('resources', 'id'),           (SELECT max(id) FROM resources));
SELECT setval(pg_get_serial_sequence('maintenance_blocks', 'id'),  (SELECT max(id) FROM maintenance_blocks));
SELECT setval(pg_get_serial_sequence('reservations', 'id'),        (SELECT max(id) FROM reservations));

COMMIT;
