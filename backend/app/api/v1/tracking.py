from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models import Match, ModelVersion, Prediction, PredictionResult
from app.services import tracking

router = APIRouter(tags=["historique et performance"])


class PredictionOut(BaseModel):
    id: int
    match_id: int
    model: str
    market: str
    selection: str
    line: float | None
    probability: float
    observed_odds: float | None
    created_at: str
    outcome: Literal["win", "loss", "void"] | None


@router.post("/matches/{match_id}/predictions", status_code=201)
def record_predictions(match_id: int, db: DbDep, user: CurrentUser):
    """Enregistre (une seule fois, de façon immuable) les prédictions d'un match à venir."""
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    try:
        rows, already = tracking.record(db, match, user.id)
    except tracking.RecordError as e:
        raise HTTPException(e.status, e.message) from None
    return {"match_id": match_id, "already_recorded": already, "count": len(rows)}


@router.get("/predictions", response_model=list[PredictionOut])
def list_predictions(
    db: DbDep,
    match_id: int | None = None,
    state: Literal["pending", "settled"] | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    q = (
        select(Prediction, PredictionResult, ModelVersion)
        .outerjoin(PredictionResult, PredictionResult.prediction_id == Prediction.id)
        .join(ModelVersion, ModelVersion.id == Prediction.model_version_id)
        .order_by(Prediction.created_at.desc(), Prediction.id)
    )
    if match_id:
        q = q.where(Prediction.match_id == match_id)
    if state == "pending":
        q = q.where(PredictionResult.id.is_(None))
    elif state == "settled":
        q = q.where(PredictionResult.id.is_not(None))
    return [
        PredictionOut(
            id=p.id,
            match_id=p.match_id,
            model=f"{mv.name}-{mv.version}",
            market=p.market,
            selection=p.selection,
            line=p.line,
            probability=p.probability,
            observed_odds=p.observed_odds,
            created_at=p.created_at.isoformat(),
            outcome=r.outcome.value if r else None,
        )
        for p, r, mv in db.execute(q.limit(limit).offset(offset))
    ]


@router.post("/predictions/settle")
def settle_all(db: DbDep, _: CurrentUser):
    """Règle les prédictions dont le match est terminé ou annulé (idempotent)."""
    return {"settled": tracking.settle_pending(db)}


@router.get("/performance")
def performance(
    db: DbDep, competition_id: int | None = None, market: Literal["1X2", "OU", "BTTS"] | None = None
):
    return tracking.performance(db, competition_id, market)
