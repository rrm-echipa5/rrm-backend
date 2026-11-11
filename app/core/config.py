from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurarea aplicației, citită din variabile de mediu sau din fișierul `.env`.

    Fiecare câmp se poate suprascrie cu o variabilă de mediu cu prefixul `RRM_`,
    de exemplu `RRM_API_PREFIX=/api`.
    """

    model_config = SettingsConfigDict(env_prefix="RRM_", env_file=".env", extra="ignore")

    app_name: str = "Research Resource Manager API"
    api_prefix: str = "/api"


@lru_cache
def get_settings() -> Settings:
    """Întoarce configurarea, citită o singură dată la pornirea aplicației."""
    return Settings()
