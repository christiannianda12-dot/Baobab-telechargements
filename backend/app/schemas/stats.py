from pydantic import BaseModel, ConfigDict, Field

from app.models.mixins import DataSource


class StatsUpsert(BaseModel):
    """Toute valeur omise reste NULL (donnée absente), jamais 0 par défaut."""

    shots: int | None = Field(default=None, ge=0, le=100)
    shots_on_target: int | None = Field(default=None, ge=0, le=100)
    corners: int | None = Field(default=None, ge=0, le=60)
    possession_pct: float | None = Field(default=None, ge=0, le=100)
    fouls: int | None = Field(default=None, ge=0, le=100)
    yellow_cards: int | None = Field(default=None, ge=0, le=20)
    red_cards: int | None = Field(default=None, ge=0, le=11)


class StatsOut(StatsUpsert):
    model_config = ConfigDict(from_attributes=True)
    match_id: int
    team_id: int
    source: DataSource
