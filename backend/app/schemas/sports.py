from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.mixins import DataSource
from app.models.sports import MatchStatus


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    short_name: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=80)


class TeamOut(_Out, TeamCreate):
    id: int
    source: DataSource


class CompetitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    country: str | None = Field(default=None, max_length=80)
    season: str | None = Field(default=None, max_length=20)


class CompetitionOut(_Out, CompetitionCreate):
    id: int
    source: DataSource


class MatchCreate(BaseModel):
    competition_id: int
    home_team_id: int
    away_team_id: int
    kickoff_at: datetime
    status: MatchStatus = MatchStatus.SCHEDULED
    home_score: int | None = Field(default=None, ge=0, le=99)
    away_score: int | None = Field(default=None, ge=0, le=99)

    @model_validator(mode="after")
    def _check(self) -> "MatchCreate":
        if self.home_team_id == self.away_team_id:
            raise ValueError("Une équipe ne peut pas jouer contre elle-même.")
        if (self.home_score is None) != (self.away_score is None):
            raise ValueError("Les deux scores doivent être renseignés ensemble.")
        return self


class MatchOut(_Out):
    id: int
    competition_id: int
    home_team_id: int
    away_team_id: int
    kickoff_at: datetime
    status: MatchStatus
    home_score: int | None
    away_score: int | None
    source: DataSource


class MatchUpdate(BaseModel):
    """Mise à jour d'un match (résultat, statut, horaire). Champs omis = inchangés."""

    kickoff_at: datetime | None = None
    status: MatchStatus | None = None
    home_score: int | None = Field(default=None, ge=0, le=99)
    away_score: int | None = Field(default=None, ge=0, le=99)
    home_score_ht: int | None = Field(default=None, ge=0, le=99)
    away_score_ht: int | None = Field(default=None, ge=0, le=99)
