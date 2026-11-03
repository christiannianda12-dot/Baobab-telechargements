from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbDep
from app.models import Competition, Match, Team
from app.models.mixins import DataSource
from app.schemas.sports import (
    CompetitionCreate,
    CompetitionOut,
    MatchCreate,
    MatchOut,
    TeamCreate,
    TeamOut,
)

router = APIRouter(tags=["données sportives (mode manuel)"])


def _create(db, obj, label: str):
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"{label} existe déjà.") from None
    return obj


@router.get("/teams", response_model=list[TeamOut])
def list_teams(db: DbDep, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    return db.scalars(select(Team).order_by(Team.name).limit(limit).offset(offset)).all()


@router.post("/teams", response_model=TeamOut, status_code=201)
def create_team(payload: TeamCreate, db: DbDep, _: CurrentUser):
    return _create(db, Team(**payload.model_dump(), source=DataSource.MANUAL), "Cette équipe")


@router.get("/competitions", response_model=list[CompetitionOut])
def list_competitions(db: DbDep):
    return db.scalars(select(Competition).order_by(Competition.name)).all()


@router.post("/competitions", response_model=CompetitionOut, status_code=201)
def create_competition(payload: CompetitionCreate, db: DbDep, _: CurrentUser):
    return _create(
        db, Competition(**payload.model_dump(), source=DataSource.MANUAL), "Cette compétition"
    )


@router.get("/matches", response_model=list[MatchOut])
def list_matches(
    db: DbDep,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    competition_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(Match).order_by(Match.kickoff_at)
    if date_from:
        q = q.where(Match.kickoff_at >= date_from)
    if date_to:
        q = q.where(Match.kickoff_at < date_to)
    if competition_id:
        q = q.where(Match.competition_id == competition_id)
    return db.scalars(q.limit(limit).offset(offset)).all()


@router.get("/matches/{match_id}", response_model=MatchOut)
def get_match(match_id: int, db: DbDep):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    return match


@router.post("/matches", response_model=MatchOut, status_code=201)
def create_match(payload: MatchCreate, db: DbDep, _: CurrentUser):
    for model, pk, label in (
        (Competition, payload.competition_id, "Compétition"),
        (Team, payload.home_team_id, "Équipe domicile"),
        (Team, payload.away_team_id, "Équipe extérieur"),
    ):
        if db.get(model, pk) is None:
            raise HTTPException(422, f"{label} inconnue.")
    return _create(db, Match(**payload.model_dump(), source=DataSource.MANUAL), "Ce match")
