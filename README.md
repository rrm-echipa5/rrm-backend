# rrm-backend

API-ul REST al aplicației **Research Resource Manager** (echipa 5, Ingineria Programelor, USV), scris în Python cu FastAPI. Contractul API este `rrm-api.yaml`, atașat Documentului de Arhitectură din Confluence.

## Cerințe

- Python 3.14 (minimum 3.13)
- [uv](https://docs.astral.sh/uv/) pentru dependențe și mediul virtual
- Docker, pentru baza de date PostgreSQL 18 locală

## Pornire

```bash
cp .env.example .env
docker compose up -d          # PostgreSQL cu schema și datele de test din db/
uv sync
uv run pre-commit install
uv run uvicorn app.main:app --reload --port 8080
```

API-ul răspunde la `http://localhost:8080/api`, iar documentația Swagger UI este la `http://localhost:8080/api/docs`. `GET /api/health` arată și dacă baza de date este disponibilă.

## Baza de date

`db/schema.sql` și `db/seed.sql` sunt scripturile din pagina **Research Resource Manager - Baza de date** din Confluence (KAN-55, KAN-56). La prima pornire, containerul le rulează în ordine, deci baza conține de la început utilizatorii, echipele, cele 5 resurse și rezervările din prototipuri. Conexiunea se configurează cu `RRM_DATABASE_URL`.

Pentru a reîncărca datele de test de la zero:

```bash
docker compose down -v && docker compose up -d
```

Fără Docker, pe un PostgreSQL instalat local:

```bash
createdb rrm
psql -d rrm -f db/schema.sql -f db/seed.sql
```

## Structura

```text
app/
  main.py         # aplicația FastAPI și routerele
  core/           # configurare
  db/             # conexiunea SQLAlchemy la PostgreSQL
db/               # schema.sql și seed.sql
scripts/          # verificarea convențiilor Git (branch, commit, titlu PR)
tests/            # teste pytest
```

## Contribuții

Fluxul de lucru, coding style-ul și verificările automate sunt descrise în [CONTRIBUTING.md](CONTRIBUTING.md).
