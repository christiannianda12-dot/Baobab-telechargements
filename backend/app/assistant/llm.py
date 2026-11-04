"""Interface d'un modèle de langage (Claude, GPT, ...). AUCUN connecteur n'est implémenté à ce stade.

Pour en brancher un : implémenter `LLMBackend.rephrase` (reformuler une réponse déjà calculée, SANS ajouter de
chiffre ni de fait), l'enregistrer dans `get_llm`, tester avec une vraie clé. Tant que ce n'est pas fait,
l'assistant fonctionne en mode « règles » et le dit explicitement.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings


class LLMBackend(Protocol):
    name: str
    enabled: bool

    def rephrase(self, facts: dict, draft: str) -> str: ...


@dataclass
class NullLLM:
    name: str = "none"
    enabled: bool = False

    def rephrase(self, facts: dict, draft: str) -> str:  # pragma: no cover - jamais appelé
        return draft


def get_llm(settings: Settings) -> LLMBackend:
    return NullLLM()


def status(settings: Settings) -> dict:
    key = bool(settings.llm_api_key.strip())
    return {
        "engine": "rules",
        "llm_enabled": False,
        "llm_key_present": key,
        "message": (
            "Une clé LLM est présente mais aucun connecteur n'est implémenté : elle est ignorée."
            if key
            else "Aucun modèle de langage connecté. Les réponses sont générées par des règles à partir des calculs du moteur statistique."
        ),
    }
