# rrm-backend

API-ul REST al aplicației **Research Resource Manager** (echipa 5, Ingineria Programelor, USV), scris în Python cu FastAPI. Contractul API este `rrm-api.yaml`, atașat Documentului de Arhitectură din Confluence.

## Cerințe

- Python 3.14 (minimum 3.13)
- [uv](https://docs.astral.sh/uv/) pentru dependențe și mediul virtual
- Docker, pentru baza de date PostgreSQL 18 locală (Docker Desktop pe Windows și macOS)
- Git

## Instalare și pornire

Pașii de mai jos pornesc de la o mașină fără proiect. Comenzile sunt aceleași în PowerShell, cu excepția lui `cp` (în PowerShell: `Copy-Item .env.example .env`).

```bash
git clone https://github.com/rrm-echipa5/rrm-backend.git
cd rrm-backend
cp .env.example .env                 # configurarea locală; .env nu intră în Git
docker compose up -d                 # PostgreSQL cu schema și datele de test din db/
docker compose ps                    # așteaptă starea "healthy"
uv sync                              # Python, dependențele și uneltele de dezvoltare
uv run pre-commit install           # hook-urile pre-commit, commit-msg și pre-push
uv run uvicorn app.main:app --reload --port 8080
```

Verificarea instalării:

- `http://localhost:8080/api/health` răspunde cu `{"status": "ok", "database": "ok"}`; `"database": "unavailable"` înseamnă că baza nu e pornită (vezi [Probleme cunoscute](#probleme-cunoscute)).
- Swagger UI se deschide la `http://localhost:8080/api/docs`.
- `uv run pytest`, `uv run ruff check` și `uv run mypy` trec.

## Aplicația completă (cu rrm-frontend)

Frontend-ul [rrm-frontend](https://github.com/rrm-echipa5/rrm-frontend) trimite cererile `/api` la backend-ul de pe portul **8080**, deci backend-ul trebuie pornit pe acest port.

```bash
# terminalul 1, în rrm-backend
docker compose up -d
uv run uvicorn app.main:app --reload --port 8080

# terminalul 2, în rrm-frontend
npm ci
npm run dev                          # http://localhost:5173
```

Până la autentificare (KAN-64), toate cererile se fac în numele utilizatorului din `RRM_DEMO_USER_ID` (în `.env`). Pentru a vedea aplicația ca alt utilizator, se schimbă valoarea și se repornește backend-ul. Utilizatorii din datele de test (`db/seed.sql`):

| Id | Nume | Rol | Ce se vede în aplicație |
| --- | --- | --- | --- |
| 1 | Elena Marin | `SYSTEM_ADMIN` | Poate modifica orice resursă și o poate scoate din catalog |
| 2 | Andrei Rusu | `RESEARCHER` | Coordonează echipa 1; o rezervare confirmată pe microscopul SEM |
| 3 | Ana Popescu | `STUDENT` | Rezervări în mai multe stări; certificată pentru SEM și Raman |
| 4 | Mihai Ionescu | `RESOURCE_ADMIN` | Implicit; administrează SEM, TEM și Raman |
| 5 | Ioana Dumitru | `STUDENT` | O cerere în așteptare; certificarea pentru TEM e revocată |
| 6 | Radu Stan | `RESEARCHER` | Coordonează echipa 2 |
| 7 | Vlad Popa | `RESOURCE_ADMIN` | Administrează clusterul HPC și sala de seminar |

## Baza de date

`db/schema.sql` și `db/seed.sql` sunt scripturile din pagina **Research Resource Manager - Baza de date** din Confluence (KAN-55, KAN-56). La prima pornire, containerul le rulează în ordine, deci baza conține de la început utilizatorii, echipele, cele 5 resurse și rezervările din prototipuri. Conexiunea se configurează cu `RRM_DATABASE_URL`.

Pentru a reîncărca datele de test de la zero (de exemplu după o modificare în `db/`):

```bash
docker compose down -v && docker compose up -d
```

Fără Docker, pe un PostgreSQL instalat local:

```bash
createdb rrm
psql -d rrm -f db/schema.sql -f db/seed.sql
```

### Migrări

Odată cu KAN-85 (#10), schema e descrisă în trei locuri care trebuie să rămână identice: `db/schema.sql`, modelele SQLAlchemy (`app/modules/*/models.py`) și migrările Alembic (`migrations/`). `db/schema.sql` rămâne scriptul din care docker compose și CI creează baza cu datele de test, iar CI le leagă pe toate trei: `tests/test_models_schema.py` compară modelele cu baza din `schema.sql`, iar `alembic check` compară migrările cu modelele, pe o bază goală. O modificare a schemei atinge deci toate trei locurile.

Baza din docker compose are deja tabelele din `schema.sql`. Înainte de prima migrare nouă se marchează o singură dată ca fiind la revizia `0001`; altfel primul `alembic upgrade head` încearcă să creeze din nou tabelele și pică:

```bash
uv run alembic stamp 0001        # o singură dată, pe o bază creată din db/schema.sql
uv run alembic upgrade head
```

O migrare nouă:

```bash
uv run alembic revision --autogenerate -m "descriere"
uv run alembic upgrade head
uv run alembic check             # "No new upgrade operations detected."
```

## Endpoint-uri

Toate căile au prefixul `/api`. Coloana „Tichet” arată unde a fost adăugat fiecare endpoint. Anularea (KAN-78), calendarul (KAN-70) și certificările (KAN-154) ajung în `main` odată cu PR-urile lor.

| Metodă și cale | Ce face | Tichet |
| --- | --- | --- |
| `GET /health` | Starea serverului și a bazei de date | KAN-123 |
| `GET /resource-categories` | Categoriile de resurse | KAN-124 |
| `GET /resources` | Catalogul, paginat (`page`, `size`, `sort=name,asc`), cu filtrele `categoryId`, `status`, `q`, `tag` și `administeredByMe` | KAN-124, KAN-87 |
| `GET /resources/{resourceId}` | Fișa resursei, cu regulile de utilizare și `userCertified` | KAN-124, KAN-88 |
| `POST /resources` | Adaugă o resursă (201, antet `Location`) | KAN-124 |
| `PUT /resources/{resourceId}` | Modifică fișa resursei | KAN-124 |
| `DELETE /resources/{resourceId}` | Scoate resursa din catalog (ștergere logică); 409 `RESOURCE_HAS_RESERVATIONS` dacă are rezervări viitoare | KAN-124 |
| `GET /resources/{resourceId}/calendar` | Intervalele ocupate dintre `start` și `end` (cel mult 31 de zile) și regulile de utilizare | KAN-70 |
| `GET /users/me/reservations` | Rezervările mele, paginate, cu filtrele `status`, `from`, `to` | KAN-77 |
| `GET /reservations/{reservationId}` | Detaliile rezervării, cu istoricul aprobărilor | KAN-77 |
| `POST /reservations/{reservationId}/cancel` | Anulează o cerere în așteptare sau o rezervare confirmată; 409 `INVALID_STATE` altfel | KAN-78 |
| `GET /users/me/certifications` | Certificările mele, cu starea `ACTIVE`, `EXPIRED` sau `REVOKED` | KAN-154 |

Erorile au corp `application/problem+json`, cu un `code` stabil (`VALIDATION_FAILED`, `NOT_FOUND`, `ACCESS_DENIED`, `RESOURCE_HAS_RESERVATIONS`, `INVALID_STATE`) și, la validare, lista `errors` cu câmpurile greșite.

## Teste

Testele rulează pe baza de date locală, fiecare într-o tranzacție anulată la final, deci datele de test rămân neschimbate:

```bash
docker compose up -d
uv run pytest
```

## Probleme cunoscute

| Problema | Cauza și rezolvarea |
| --- | --- |
| `GET /api/health` arată `"database": "unavailable"` sau testele pică cu `connection refused` / `ConnectionTimeout` | Baza nu rulează. `docker compose ps` trebuie să arate `rrm-db` cu starea `healthy`; altfel `docker compose up -d` și se așteaptă câteva secunde. |
| `docker compose up -d` pornește baza, dar după un minut conexiunea dispare (Docker instalat direct în WSL, fără Docker Desktop) | WSL oprește distribuția când nu mai rulează nicio sesiune. Baza se pornește în prim-plan, într-un terminal separat: `wsl -d Ubuntu -- docker compose up`. |
| Portul `5432` este ocupat | Rulează deja un PostgreSQL local. Se oprește serviciul sau se schimbă portul din `docker-compose.yml` și din `RRM_DATABASE_URL`. |
| Portul `8080` este ocupat | Pe Windows, `netstat -ano \| findstr :8080` arată procesul. Se oprește procesul sau se pornește backend-ul pe alt port, iar frontend-ul primește adresa în `RRM_API_TARGET` (de exemplu `http://localhost:8081`). |
| `ruff format --check` raportează toate fișierele pe Windows, deși `git diff` e gol | Copia a fost clonată înainte de `.gitattributes` (KAN-159) și are fișiere cu CRLF, iar Ruff cere LF. Clonele noi au LF pe orice sistem. O copie mai veche se repară după ce toate modificările sunt comise (altfel se pierd): `git rm -r --cached . && git reset --hard`. |
| După rescrierea lui `main` din 16.11, `git pull` dă conflicte sau commit-uri duplicate | Copia locală are istoricul vechi. Fără modificări locale: `git fetch origin`, `git checkout main`, `git reset --hard origin/main`. Un branch început înainte de 16.11 se mută peste noul `main` cu `git rebase --onto origin/main <ultimul-commit-vechi-din-main> <branch>`. |
| Datele de test nu corespund cu `db/seed.sql` după un `git pull` | Containerul rulează scripturile doar la prima pornire. `docker compose down -v && docker compose up -d` le reîncarcă. |

## Structura

```text
app/
  main.py         # aplicația FastAPI și routerele
  core/           # configurare
  core/errors.py  # erorile application/problem+json
  db/             # conexiunea SQLAlchemy la PostgreSQL
  modules/
    reservations/ # rezervările mele, detaliile, anularea și calendarul resursei
    resources/    # catalogul, fișa resursei și certificările mele
    projects/     # echipele și proiectele (referința din rezervări)
    users/        # modelul utilizatorului
db/               # schema.sql și seed.sql
scripts/          # verificarea convențiilor Git (branch, commit, titlu PR)
tests/            # teste pytest
```

## Contribuții

Fluxul de lucru, coding style-ul și verificările automate sunt descrise în [CONTRIBUTING.md](CONTRIBUTING.md).
