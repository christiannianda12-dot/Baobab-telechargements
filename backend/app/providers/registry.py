from app.core.config import Settings
from app.providers.base import DataProvider
from app.providers.connectors import ApiFootballProvider, TheOddsApiProvider


def build_providers(s: Settings) -> list[DataProvider]:
    return [
        ApiFootballProvider(s.api_football_key, s.api_football_base_url),
        TheOddsApiProvider(s.odds_api_key, s.odds_api_base_url),
    ]
