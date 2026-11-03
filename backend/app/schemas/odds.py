from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.mixins import DataSource

Market = Literal["1X2", "DC", "OU", "BTTS", "CORNERS_OU"]

SELECTIONS: dict[str, set[str]] = {
    "1X2": {"home", "draw", "away"},
    "DC": {"1X", "12", "X2"},
    "OU": {"over", "under"},
    "BTTS": {"yes", "no"},
    "CORNERS_OU": {"over", "under"},
}
LINE_REQUIRED = {"OU", "CORNERS_OU"}


class OddsCreate(BaseModel):
    bookmaker: str = Field(min_length=1, max_length=80)
    market: Market
    selection: str = Field(min_length=1, max_length=40)
    line: float | None = Field(default=None, ge=0, le=100)
    price: float = Field(gt=1, le=1000, description="Cote décimale")

    @model_validator(mode="after")
    def _check(self) -> "OddsCreate":
        if self.selection not in SELECTIONS[self.market]:
            raise ValueError(
                f"Sélection invalide pour {self.market} : {sorted(SELECTIONS[self.market])}"
            )
        if self.market in LINE_REQUIRED and self.line is None:
            raise ValueError(f"Une ligne (ex. 2.5) est requise pour le marché {self.market}.")
        if self.market not in LINE_REQUIRED and self.line is not None:
            raise ValueError(f"Le marché {self.market} n'a pas de ligne.")
        return self


class OddsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int
    bookmaker: str
    market: str
    selection: str
    line: float | None
    price: float
    recorded_at: datetime
    source: DataSource


class CalcRequest(BaseModel):
    """Calculateur sans état : aucune donnée enregistrée."""

    prices: list[float] = Field(
        min_length=2, max_length=20, description="Cotes d'un marché complet"
    )
    estimated_probabilities: list[float] | None = Field(
        default=None, description="Probabilités estimées dans le même ordre (optionnel)"
    )

    @model_validator(mode="after")
    def _check(self) -> "CalcRequest":
        if any(p <= 1 for p in self.prices):
            raise ValueError("Toutes les cotes doivent être > 1.")
        probs = self.estimated_probabilities
        if probs is not None:
            if len(probs) != len(self.prices):
                raise ValueError("Autant de probabilités que de cotes.")
            if any(not 0 <= p <= 1 for p in probs):
                raise ValueError("Probabilités comprises entre 0 et 1.")
        return self


class CalcResponse(BaseModel):
    implied_probabilities: list[float]
    margin: float
    fair_probabilities: list[float]
    expected_values: list[float] | None = None
    edges: list[float] | None = None
