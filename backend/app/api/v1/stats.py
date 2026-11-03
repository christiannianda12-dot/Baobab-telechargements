from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models import Match, MatchStatistics
from app.models.mixins import DataSource
from app.schemas.stats import StatsOut, StatsUpsert

router = APIRouter(tags=["statistiques de match"])


@router.get("/matches/{match_id}/statistics", response_model=list[StatsOut])
def get_stats(match_id: int, db: DbDep):
    if not db.get(Match, match_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    return db.scalars(select(MatchStatistics).where(MatchStatistics.match_id == match_id)).all()


@router.put("/matches/{match_id}/statistics/{team_id}", response_model=StatsOut)
def put_stats(match_id: int, team_id: int, payload: StatsUpsert, db: DbDep, _: CurrentUser):
    """Crée ou remplace les statistiques d'une équipe pour ce match (valeurs omises = absentes)."""
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    if team_id not in (match.home_team_id, match.away_team_id):
        raise HTTPException(422, "Cette équipe ne participe pas à ce match.")
    row = db.scalar(
        select(MatchStatistics).where(
            MatchStatistics.match_id == match_id, MatchStatistics.team_id == team_id
        )
    )
    if row is None:
        row = MatchStatistics(match_id=match_id, team_id=team_id, source=DataSource.MANUAL)
        db.add(row)
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    db.commit()
    return row
