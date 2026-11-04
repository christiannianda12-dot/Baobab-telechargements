from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models import AnalysisHistory, Match
from app.models.mixins import utcnow
from app.models.sports import MatchStatus
from app.services import combos

router = APIRouter(prefix="/combos", tags=["combinés"])


class Leg(BaseModel):
    match_id: int
    market: Literal["1X2", "DC", "OU", "BTTS"]
    selection: str
    line: float | None = None

    @model_validator(mode="after")
    def _check(self) -> "Leg":
        try:
            combos.predicate(self.market, self.selection, self.line)
        except (ValueError, KeyError):
            raise ValueError("Sélection non supportée (OU : lignes 0.5 à 4.5).") from None
        return self


class AnalyzeRequest(BaseModel):
    legs: list[Leg] = Field(min_length=1, max_length=combos.MAX_LEGS)


class SuggestRequest(BaseModel):
    size: int = Field(default=3, ge=2, le=combos.MAX_LEGS)
    match_ids: list[int] | None = Field(default=None, max_length=50)
    min_probability: float = Field(default=0.0, ge=0, le=1)


@router.post("/analyze")
def analyze(payload: AnalyzeRequest, db: DbDep, user: CurrentUser):
    res = combos.analyze(db, [g.model_dump() for g in payload.legs])
    db.add(
        AnalysisHistory(
            user_id=user.id,
            kind="combo",
            payload={"legs": [g.model_dump() for g in payload.legs], "valid": res["valid"]},
        )
    )
    db.commit()
    return res


@router.post("/suggest")
def suggest(payload: SuggestRequest, db: DbDep, user: CurrentUser):
    ids = payload.match_ids
    if ids is None:  # par défaut : prochains matchs programmés
        q = (
            select(Match.id)
            .where(Match.status == MatchStatus.SCHEDULED, Match.kickoff_at > utcnow())
            .order_by(Match.kickoff_at)
            .limit(30)
        )
        ids = list(db.scalars(q))
    if not ids:
        raise HTTPException(422, "Aucun match à venir enregistré.")
    res = combos.suggest(db, ids, payload.size, payload.min_probability)
    db.add(
        AnalysisHistory(
            user_id=user.id,
            kind="combo_suggest",
            payload={"size": payload.size, "valid": res["valid"]},
        )
    )
    db.commit()
    return res
