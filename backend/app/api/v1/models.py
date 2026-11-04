from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.ml import backtest, elo
from app.ml.data import load_finished
from app.models import Competition, Match, Team
from app.services.predict import build_prediction

router = APIRouter(tags=["moteur statistique"])


@router.get("/matches/{match_id}/prediction")
def prediction(match_id: int, db: DbDep):
    """Probabilités du modèle de Poisson, calculées uniquement sur les matchs antérieurs au coup d'envoi.
    Refuse de prédire (available=false) quand l'historique est insuffisant."""
    m = db.get(Match, match_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    out = build_prediction(db, m)
    out.pop("lambdas", None)
    return out


@router.get("/competitions/{competition_id}/elo")
def competition_elo(competition_id: int, db: DbDep):
    if not db.get(Competition, competition_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétition introuvable.")
    recs = load_finished(db, competition_id)
    r = elo.ratings(recs)
    names = (
        {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(list(r))))} if r else {}
    )
    ranking = sorted(
        ({"team_id": t, "team": names.get(t), "rating": v} for t, v in r.items()),
        key=lambda x: -x["rating"],
    )
    return {
        "competition_id": competition_id,
        "matches_used": len(recs),
        "ranking": ranking,
        "note": "Classement de force relative (Elo, départ à 1500). Fiable seulement avec plusieurs matchs par équipe.",
    }


@router.get("/competitions/{competition_id}/backtest")
def competition_backtest(competition_id: int, db: DbDep, _: CurrentUser):
    """Évalue le modèle en walk-forward sur l'historique enregistré (Brier, Log Loss, calibration)."""
    if not db.get(Competition, competition_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétition introuvable.")
    return backtest.run(load_finished(db, competition_id))
