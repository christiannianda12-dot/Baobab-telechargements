from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models import Match, Odds
from app.models.mixins import DataSource
from app.schemas.odds import CalcRequest, CalcResponse, OddsCreate, OddsOut
from app.services import odds as calc
from app.services.odds_analysis import analyse

router = APIRouter(tags=["cotes"])


def _match_or_404(db, match_id: int) -> Match:
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    return match


@router.post("/matches/{match_id}/odds", response_model=OddsOut, status_code=201)
def add_odds(match_id: int, payload: OddsCreate, db: DbDep, _: CurrentUser):
    """Saisie manuelle d'une cote (historisée : chaque saisie est conservée)."""
    _match_or_404(db, match_id)
    odds = Odds(match_id=match_id, source=DataSource.MANUAL, **payload.model_dump())
    db.add(odds)
    db.commit()
    return odds


@router.get("/matches/{match_id}/odds", response_model=list[OddsOut])
def list_odds(match_id: int, db: DbDep):
    _match_or_404(db, match_id)
    q = select(Odds).where(Odds.match_id == match_id).order_by(Odds.recorded_at, Odds.id)
    return db.scalars(q).all()


@router.get("/matches/{match_id}/odds/analysis")
def odds_analysis(match_id: int, db: DbDep):
    """Probabilités implicites, marge et probabilités corrigées, sur les cotes saisies uniquement."""
    _match_or_404(db, match_id)
    rows = list(db.scalars(select(Odds).where(Odds.match_id == match_id)))
    return {"match_id": match_id, "markets": analyse(rows)}


@router.post("/odds/calculate", response_model=CalcResponse)
def calculate(payload: CalcRequest):
    prices = payload.prices
    out = CalcResponse(
        implied_probabilities=[calc.implied_probability(p) for p in prices],
        margin=calc.margin(prices),
        fair_probabilities=calc.remove_margin(prices),
    )
    if payload.estimated_probabilities is not None:
        probs = payload.estimated_probabilities
        out.expected_values = [
            calc.expected_value(q, p) for q, p in zip(probs, prices, strict=True)
        ]
        out.edges = [calc.edge(q, p) for q, p in zip(probs, prices, strict=True)]
    return out
