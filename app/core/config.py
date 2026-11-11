from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurarea aplicației, citită din variabile de mediu sau din fișierul `.env`.

    Fiecare câmp se poate suprascrie cu o variabilă de mediu cu prefixul `RRM_`,
    de exemplu `RRM_DATABASE_URL=postgresql+psycopg://rrm:rrm@localhost:5432/rrm`.
    """

    model_config = SettingsConfigDict(env_prefix="RRM_", env_file=".env", extra="ignore")

    app_name: str = "Research Resource Manager API"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://rrm:rrm@localhost:5432/rrm"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Până la autentificare (KAN-64), cererile se fac în numele acestui utilizator.
    # Implicit: Mihai Ionescu (RESOURCE_ADMIN) din datele de test.
    demo_user_id: int = 4


@lru_cache
def get_settings() -> Settings:
    """Întoarce configurarea, citită o singură dată la pornirea aplicației."""
    return Settings()
