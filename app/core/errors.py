"""Erorile API-ului, în formatul `application/problem+json` (RFC 9457) din `rrm-api.yaml`.

Serviciile ridică excepțiile de mai jos, iar handler-ele înregistrate în `main.py` le transformă
în răspunsuri cu un `code` stabil, pe care frontend-ul îl poate trata.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"

# Mesajele de validare pentru utilizator sunt în română, ca restul interfeței.
VALIDATION_MESSAGES = {
    "missing": "Câmpul este obligatoriu.",
    "string_too_short": "Textul trebuie să aibă cel puțin {min_length} caractere.",
    "string_too_long": "Textul poate avea cel mult {max_length} caractere.",
    "too_long": "Lista poate avea cel mult {max_length} elemente.",
    "greater_than_equal": "Valoarea trebuie să fie cel puțin {ge}.",
    "less_than_equal": "Valoarea poate fi cel mult {le}.",
    "int_parsing": "Valoarea trebuie să fie un număr întreg.",
    "int_type": "Valoarea trebuie să fie un număr întreg.",
    "string_type": "Valoarea trebuie să fie un text.",
    "enum": "Valoarea nu este permisă. Valori posibile: {expected}.",
    "literal_error": "Valoarea nu este permisă. Valori posibile: {expected}.",
    "string_pattern_mismatch": "Valoarea nu are formatul cerut.",
    "dict_type": "Valoarea trebuie să fie un obiect cu perechi denumire - valoare.",
    "list_type": "Valoarea trebuie să fie o listă.",
}


class FieldError(BaseModel):
    """Eroarea de validare a unui câmp."""

    field: str
    message: str


class Problem(BaseModel):
    """Corpul unei erori, după RFC 9457."""

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str | None = None
    instance: str | None = None
    timestamp: datetime
    errors: list[FieldError] | None = None


class ApiError(Exception):
    """Eroare de business transformată în răspuns `application/problem+json`.

    Args:
        status: Codul HTTP al răspunsului.
        code: Codul stabil al erorii (de exemplu `NOT_FOUND`).
        detail: Mesajul pentru utilizator, în română.
        errors: Erorile pe câmpuri, doar pentru validare.
    """

    def __init__(
        self,
        status: HTTPStatus,
        code: str,
        detail: str,
        errors: list[FieldError] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.errors = errors


class NotFoundError(ApiError):
    """Resursa cerută nu există sau a fost ștearsă (404 `NOT_FOUND`)."""

    def __init__(self, detail: str) -> None:
        super().__init__(HTTPStatus.NOT_FOUND, "NOT_FOUND", detail)


class ConflictError(ApiError):
    """Starea curentă nu permite operația (409)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(HTTPStatus.CONFLICT, code, detail)


class ValidationFailedError(ApiError):
    """Cererea are câmpuri invalide (400 `VALIDATION_FAILED`)."""

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__(
            HTTPStatus.BAD_REQUEST,
            "VALIDATION_FAILED",
            "Cererea conține câmpuri invalide.",
            errors,
        )


def problem_response(request: Request, error: ApiError) -> JSONResponse:
    """Construiește răspunsul `application/problem+json` pentru o eroare."""
    problem = Problem(
        title=error.status.phrase,
        status=error.status.value,
        code=error.code,
        detail=error.detail,
        instance=request.url.path,
        timestamp=datetime.now(UTC),
        errors=error.errors,
    )
    return JSONResponse(
        status_code=error.status.value,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def to_field_error(error: dict[str, Any]) -> FieldError:
    """Transformă o eroare Pydantic într-o eroare pe câmp, cu mesaj în română."""
    location = [
        str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")
    ]
    template = VALIDATION_MESSAGES.get(error.get("type", ""))
    context = error.get("ctx") or {}
    message = template.format(**context) if template else str(error.get("msg", ""))
    return FieldError(field=".".join(location) or "body", message=message)


def register_exception_handlers(app: FastAPI) -> None:
    """Înregistrează handler-ele care transformă excepțiile în `application/problem+json`."""

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return problem_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        field_errors = [to_field_error(item) for item in error.errors()]
        return problem_response(request, ValidationFailedError(field_errors))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        status = HTTPStatus(error.status_code)
        code = "NOT_FOUND" if status == HTTPStatus.NOT_FOUND else status.name
        return problem_response(request, ApiError(status, code, str(error.detail)))
