# rrm-backend

API-ul REST al aplicației **Research Resource Manager** (echipa 5, Ingineria Programelor, USV), scris în Python cu FastAPI. Contractul API este `rrm-api.yaml`, atașat Documentului de Arhitectură din Confluence.

## Cerințe

- Python 3.14 (minimum 3.13)
- [uv](https://docs.astral.sh/uv/) pentru dependențe și mediul virtual

## Pornire

```bash
uv sync
uv run pre-commit install
uv run uvicorn app.main:app --reload --port 8080
```

API-ul răspunde la `http://localhost:8080/api`, iar documentația Swagger UI este la `http://localhost:8080/api/docs`.

## Structura

```text
app/
  main.py         # aplicația FastAPI și routerele
  core/           # configurare
scripts/          # verificarea convențiilor Git (branch, commit, titlu PR)
tests/            # teste pytest
```

## Contribuții

Fluxul de lucru, coding style-ul și verificările automate sunt descrise în [CONTRIBUTING.md](CONTRIBUTING.md).
