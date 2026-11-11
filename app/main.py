from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.session import get_session, is_database_available
from app.modules.resources.router import router as resources_router


class HealthStatus(BaseModel):
    """Răspunsul endpoint-ului de verificare a stării serverului."""

    status: Literal["ok"]
    database: Literal["ok", "unavailable"]


def create_app() -> FastAPI:
    """Construiește aplicația FastAPI cu toate routerele sub prefixul `/api`."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Location"],
    )
    register_exception_handlers(app)

    api_router = APIRouter(prefix=settings.api_prefix)

    @api_router.get("/health", tags=["Sistem"])
    def get_health(session: Annotated[Session, Depends(get_session)]) -> HealthStatus:
        """Verifică dacă serverul rulează și dacă baza de date este disponibilă."""
        if is_database_available(session):
            return HealthStatus(status="ok", database="ok")
        return HealthStatus(status="ok", database="unavailable")

    api_router.include_router(resources_router)
    app.include_router(api_router)
    return app


app = create_app()
