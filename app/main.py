from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from app.core.config import get_settings


class HealthStatus(BaseModel):
    """Răspunsul endpoint-ului de verificare a stării serverului."""

    status: str


def create_app() -> FastAPI:
    """Construiește aplicația FastAPI cu toate routerele sub prefixul `/api`."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, docs_url=f"{settings.api_prefix}/docs")

    api_router = APIRouter(prefix=settings.api_prefix)

    @api_router.get("/health", tags=["Sistem"])
    def get_health() -> HealthStatus:
        """Verifică dacă serverul rulează."""
        return HealthStatus(status="ok")

    app.include_router(api_router)
    return app


app = create_app()
