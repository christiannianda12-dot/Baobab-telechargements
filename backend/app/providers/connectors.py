"""Connecteurs de fournisseurs.

Étape 1 : seuls le squelette et le statut de configuration existent. Aucun appel
réseau n'est émis et aucune donnée n'est simulée. Les conditions tarifaires et
quotas de chaque API doivent être vérifiées avant l'implémentation (étape 4).
"""

from app.providers.base import DataProvider


class ApiFootballProvider(DataProvider):
    code = "api_football"
    name = "API-Football"
    kind = "fixtures"
    docs_url = "https://www.api-football.com/documentation-v3"

    def describe(self) -> str:
        return "Calendriers, résultats, statistiques, compositions (quota selon l'offre souscrite)."


class TheOddsApiProvider(DataProvider):
    code = "the_odds_api"
    name = "The Odds API"
    kind = "odds"
    docs_url = "https://the-odds-api.com/liveapi/guides/v4/"

    def describe(self) -> str:
        return "Cotes de bookmakers (quota selon l'offre souscrite)."
