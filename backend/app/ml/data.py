"""Chargement des matchs terminés sous forme d'enregistrements légers, triés chronologiquement."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, Match, MatchStatistics
from app.models.sports import MatchStatus


@dataclass(frozen=True)
class Rec:
    when: datetime
    home: int
    away: int
    hg: int
    ag: int
    match_id: int = 0
    hsot: float | None = None  # tirs cadrés domicile (si connus)
    asot: float | None = None


def sibling_ids(db: Session, competition_id: int) -> list[int]:
    """Identifiants de toutes les saisons du même championnat (même nom, saison différente).

    Une saison est une « compétition » distincte en base ; sans regroupement, un match de début de saison
    n'aurait aucun historique. Nom comparé en Python (SQLite : lower() ne gère que l'ASCII)."""
    comp = db.get(Competition, competition_id)
    if comp is None:
        return [competition_id]
    key = comp.name.strip().casefold()
    return [c.id for c in db.scalars(select(Competition)) if c.name.strip().casefold() == key] or [
        competition_id
    ]


def load_finished(db: Session, competition_id: int, before: datetime | None = None) -> list[Rec]:
    q = select(Match).where(
        Match.competition_id.in_(sibling_ids(db, competition_id)),
        Match.status == MatchStatus.FINISHED,
        Match.home_score.is_not(None),
        Match.away_score.is_not(None),
    )
    if before is not None:
        q = q.where(Match.kickoff_at < before)
    matches = list(db.scalars(q.order_by(Match.kickoff_at, Match.id)))
    sot: dict[tuple[int, int], int | None] = {}
    if matches:
        for st in db.scalars(
            select(MatchStatistics).where(MatchStatistics.match_id.in_([m.id for m in matches]))
        ):
            sot[(st.match_id, st.team_id)] = st.shots_on_target
    return [
        Rec(
            m.kickoff_at,
            m.home_team_id,
            m.away_team_id,
            m.home_score,
            m.away_score,
            m.id,
            sot.get((m.id, m.home_team_id)),
            sot.get((m.id, m.away_team_id)),
        )
        for m in matches
    ]
