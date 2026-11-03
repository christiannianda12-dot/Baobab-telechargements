"""Chargement des matchs terminés sous forme d'enregistrements légers, triés chronologiquement."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Match
from app.models.sports import MatchStatus


@dataclass(frozen=True)
class Rec:
    when: datetime
    home: int
    away: int
    hg: int
    ag: int


def load_finished(db: Session, competition_id: int, before: datetime | None = None) -> list[Rec]:
    q = select(Match).where(
        Match.competition_id == competition_id,
        Match.status == MatchStatus.FINISHED,
        Match.home_score.is_not(None),
        Match.away_score.is_not(None),
    )
    if before is not None:
        q = q.where(Match.kickoff_at < before)
    rows = db.scalars(q.order_by(Match.kickoff_at, Match.id))
    return [
        Rec(m.kickoff_at, m.home_team_id, m.away_team_id, m.home_score, m.away_score) for m in rows
    ]
