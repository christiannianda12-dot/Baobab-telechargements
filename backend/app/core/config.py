"""Configuration centralisée, lue depuis les variables d'environnement."""

from enum import Enum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "change-me-in-.env-before-any-real-use"


class DataMode(str, Enum):
    MANUAL = "manual"  # saisie manuelle, aucune API externe
    DEMO = "demo"  # données fictives, toujours marquées is_demo=True
    API = "api"  # fournisseurs externes (clés requises)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "PREDIX AI"
    environment: str = "development"  # development | test | production
    database_url: str = "sqlite:///./data/predix.db"
    secret_key: str = INSECURE_DEFAULT_SECRET
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    data_mode: DataMode = DataMode.MANUAL
    auth_rate_limit_per_minute: int = Field(default=10, ge=1)

    # Fournisseurs externes : désactivés tant que la clé est vide.
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @model_validator(mode="after")
    def _forbid_default_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (
            self.secret_key == INSECURE_DEFAULT_SECRET or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY doit être défini (>= 32 caractères) en production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
