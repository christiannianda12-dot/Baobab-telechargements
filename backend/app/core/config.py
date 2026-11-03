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
    session_cookie_name: str = "predix_session"
    cookie_secure: bool | None = None  # None => True en production (HTTPS obligatoire), False sinon
    cookie_samesite: str = "lax"
    # Usage interne : accepte le site ouvert via l'IP du PC sur le réseau local (jamais en production)
    allow_lan_origins: bool = False
    trust_proxy_headers: bool = (
        False  # True derrière un reverse proxy de confiance (X-Forwarded-For)
    )

    # Modèle de langage (optionnel). Aucun connecteur implémenté : la clé est ignorée tant qu'il n'existe pas.
    llm_provider: str = ""
    llm_api_key: str = ""

    # Fournisseurs externes : désactivés tant que la clé est vide.
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        """Origines du réseau local privé (localhost, 192.168.x.x, 10.x.x.x, 172.16-31.x.x) sur le port 3000."""
        if not self.allow_lan_origins:
            return None
        return r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):3000"

    @property
    def cookie_secure_effective(self) -> bool:
        return (
            self.environment == "production" if self.cookie_secure is None else self.cookie_secure
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @model_validator(mode="after")
    def _forbid_default_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (
            self.secret_key == INSECURE_DEFAULT_SECRET or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY doit être défini (>= 32 caractères) en production.")
        if self.environment == "production" and self.allow_lan_origins:
            raise ValueError(
                "ALLOW_LAN_ORIGINS est réservé à l'usage interne : interdit en production."
            )
        if self.environment == "production" and any(
            o in ("*", "") or o.startswith("http://localhost") for o in self.cors_origin_list
        ):
            raise ValueError(
                "CORS_ORIGINS doit lister les origines HTTPS réelles en production (pas de * ni localhost)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
