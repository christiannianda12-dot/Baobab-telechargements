from abc import ABC, abstractmethod


class ProviderNotConfigured(RuntimeError):
    """Levée quand on sollicite un fournisseur dont la clé API est absente."""


class DataProvider(ABC):
    code: str
    name: str
    kind: str
    docs_url: str

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def require_configured(self) -> None:
        if not self.is_configured:
            raise ProviderNotConfigured(f"{self.name}: clé API absente (voir .env).")

    @abstractmethod
    def describe(self) -> str: ...
