"""Forme des équipes et confrontations directes, calculées UNIQUEMENT sur des matchs terminés
et antérieurs à `before` (aucune fuite d'information du futur). Données absentes = non comptées."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Match, MatchStatistics
from app.models.sports import MatchStatus

STAT_COLS = [
    "shots",
    "shots_on_target",
    "corners",
    "possession_pct",
    "fouls",
    "yellow_cards",
    "red_cards",
]
MIN_RELIABLE = 5


def _finished(db: Session, cond, before: datetime, limit: int) -> list[Match]:
    q = (
        select(Match)
        .where(
            cond,
            Match.status == MatchStatus.FINISHED,
            Match.kickoff_at < before,
            Match.home_score.is_not(None),
            Match.away_score.is_not(None),
        )
        .order_by(Match.kickoff_at.desc(), Match.id.desc())
        .limit(limit)
    )
    return list(db.scalars(q))


def team_form(
    db: Session, team_id: int, before: datetime, window: int = 10, venue: str = "all"
) -> dict:
    cond = {
        "all": or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        "home": Match.home_team_id == team_id,
        "away": Match.away_team_id == team_id,
    }[venue]
    matches = _finished(db, cond, before, window)
    w = d = lo = gf = ga = 0
    results = []
    for m in matches:
        home = m.home_team_id == team_id
        f, a = (m.home_score, m.away_score) if home else (m.away_score, m.home_score)
        gf, ga = gf + f, ga + a
        r = "W" if f > a else "D" if f == a else "L"
        w, d, lo = w + (r == "W"), d + (r == "D"), lo + (r == "L")
        results.append(r)
    n = len(matches)
    stats_rows = (
        list(
            db.scalars(
                select(MatchStatistics).where(
                    MatchStatistics.team_id == team_id,
                    MatchStatistics.match_id.in_([m.id for m in matches]),
                )
            )
        )
        if matches
        else []
    )
    averages = {}
    for col in STAT_COLS:
        vals = [getattr(s, col) for s in stats_rows if getattr(s, col) is not None]
        averages[col] = {
            "average": round(sum(vals) / len(vals), 2) if vals else None,
            "samples": len(vals),
        }
    return {
        "venue": venue,
        "window": window,
        "played": n,
        "results": results,
        "wins": w,
        "draws": d,
        "losses": lo,
        "goals_for": gf,
        "goals_against": ga,
        "avg_goals_for": round(gf / n, 2) if n else None,
        "avg_goals_against": round(ga / n, 2) if n else None,
        "averages": averages,
        "reliable": n >= MIN_RELIABLE,
    }


def head_to_head(db: Session, team_a: int, team_b: int, before: datetime, limit: int = 10) -> dict:
    cond = or_(
        (Match.home_team_id == team_a) & (Match.away_team_id == team_b),
        (Match.home_team_id == team_b) & (Match.away_team_id == team_a),
    )
    matches = _finished(db, cond, before, limit)
    a_w = b_w = dr = a_goals = b_goals = 0
    for m in matches:
        ga, gb = (
            (m.home_score, m.away_score)
            if m.home_team_id == team_a
            else (m.away_score, m.home_score)
        )
        a_goals, b_goals = a_goals + ga, b_goals + gb
        a_w, b_w, dr = a_w + (ga > gb), b_w + (gb > ga), dr + (ga == gb)
    return {
        "played": len(matches),
        "team_a_wins": a_w,
        "team_b_wins": b_w,
        "draws": dr,
        "team_a_goals": a_goals,
        "team_b_goals": b_goals,
        "matches": [
            {
                "match_id": m.id,
                "kickoff_at": m.kickoff_at.isoformat(),
                "home_team_id": m.home_team_id,
                "home_score": m.home_score,
                "away_team_id": m.away_team_id,
                "away_score": m.away_score,
            }
            for m in matches
        ],
    }


def match_analysis(db: Session, match: Match, window: int = 10) -> dict:
    h, a, t = match.home_team_id, match.away_team_id, match.kickoff_at
    out = {
        "match_id": match.id,
        "as_of": t.isoformat(),
        "window": window,
        "home": {
            "team_id": h,
            "overall": team_form(db, h, t, window),
            "at_home": team_form(db, h, t, window, "home"),
        },
        "away": {
            "team_id": a,
            "overall": team_form(db, a, t, window),
            "away": team_form(db, a, t, window, "away"),
        },
        "head_to_head": head_to_head(db, h, a, t, window),
    }
    warnings = []
    for label, f in (("domicile", out["home"]["overall"]), ("extérieur", out["away"]["overall"])):
        if not f["reliable"]:
            warnings.append(
                f"Équipe {label} : seulement {f['played']} match(s) enregistré(s) avant celui-ci (minimum conseillé : {MIN_RELIABLE})."
            )
    if out["head_to_head"]["played"] == 0:
        warnings.append("Aucune confrontation directe enregistrée.")
    out["warnings"] = warnings
    return out
