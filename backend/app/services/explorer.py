"""Lecture enrichie des données : championnats, classements, fiche équipe, recherche de matchs."""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.ml import elo
from app.ml.data import load_finished, sibling_ids
from app.models import Competition, Match, Team
from app.models.mixins import utcnow
from app.models.sports import MatchStatus
from app.services.form import team_form
from app.services.names import norm_key


def leagues(db: Session) -> list[dict]:
    comps = list(db.scalars(select(Competition)))
    stats: dict[int, dict] = defaultdict(
        lambda: {"matches": 0, "finished": 0, "upcoming": 0, "last": None}
    )
    now = utcnow()
    for cid, status, kick in db.execute(
        select(Match.competition_id, Match.status, Match.kickoff_at)
    ):
        s = stats[cid]
        s["matches"] += 1
        if status == MatchStatus.FINISHED:
            s["finished"] += 1
            s["last"] = max(s["last"], kick) if s["last"] else kick
        elif status == MatchStatus.SCHEDULED and kick > now:
            s["upcoming"] += 1
    fam: dict[str, list[Competition]] = defaultdict(list)
    for c in comps:
        fam[norm_key(c.name)].append(c)
    out = []
    for group in fam.values():
        group.sort(key=lambda c: c.season or "", reverse=True)
        seasons = [
            {
                "id": c.id,
                "season": c.season,
                **{k: stats[c.id][k] for k in ("matches", "finished", "upcoming")},
            }
            for c in group
        ]
        lasts = [stats[c.id]["last"] for c in group if stats[c.id]["last"]]
        out.append(
            {
                "id": group[0].id,
                "name": group[0].name,
                "country": group[0].country,
                "seasons": seasons,
                "matches": sum(s["matches"] for s in seasons),
                "upcoming": sum(s["upcoming"] for s in seasons),
                "last_result_at": max(lasts).isoformat() if lasts else None,
            }
        )
    return sorted(out, key=lambda x: x["name"].casefold())


def standings(db: Session, competition_id: int) -> dict | None:
    comp = db.get(Competition, competition_id)
    if comp is None:
        return None
    rows: dict[int, dict] = {}
    names = {t.id: t.name for t in db.scalars(select(Team))}
    ms = list(
        db.scalars(
            select(Match)
            .where(
                Match.competition_id == competition_id,
                Match.status == MatchStatus.FINISHED,
                Match.home_score.is_not(None),
            )
            .order_by(Match.kickoff_at, Match.id)
        )
    )

    def row(tid):
        return rows.setdefault(
            tid,
            {
                "team_id": tid,
                "team": names.get(tid, "?"),
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "gf": 0,
                "ga": 0,
                "points": 0,
                "form": [],
            },
        )

    for m in ms:
        for tid, f, a in (
            (m.home_team_id, m.home_score, m.away_score),
            (m.away_team_id, m.away_score, m.home_score),
        ):
            r = row(tid)
            r["played"] += 1
            r["gf"] += f
            r["ga"] += a
            res = "W" if f > a else "D" if f == a else "L"
            r["points"] += 3 if res == "W" else 1 if res == "D" else 0
            r[{"W": "won", "D": "drawn", "L": "lost"}[res]] += 1
            r["form"].append(res)
    table = sorted(
        rows.values(),
        key=lambda r: (-r["points"], -(r["gf"] - r["ga"]), -r["gf"], r["team"].casefold()),
    )
    for i, r in enumerate(table, 1):
        r["rank"], r["gd"], r["form"] = i, r["gf"] - r["ga"], r["form"][-5:][::-1]
    return {
        "competition_id": competition_id,
        "name": comp.name,
        "season": comp.season,
        "matches": len(ms),
        "table": table,
        "note": "Classement calculé d'après les résultats importés ; départages simplifiés (points, différence de buts, buts marqués).",
    }


def team_profile(db: Session, team_id: int) -> dict | None:
    t = db.get(Team, team_id)
    if t is None:
        return None
    now = utcnow()
    names = {x.id: x.name for x in db.scalars(select(Team))}
    comp_names = {c.id: (c.name, c.season) for c in db.scalars(select(Competition))}
    ms = list(
        db.scalars(
            select(Match)
            .where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
            .order_by(Match.kickoff_at.desc())
        )
    )

    def item(m: Match) -> dict:
        home = m.home_team_id == team_id
        opp = m.away_team_id if home else m.home_team_id
        f, a = (m.home_score, m.away_score) if home else (m.away_score, m.home_score)
        res = None if f is None else "W" if f > a else "D" if f == a else "L"
        return {
            "match_id": m.id,
            "kickoff_at": m.kickoff_at.isoformat(),
            "status": m.status.value,
            "home": home,
            "opponent_id": opp,
            "opponent": names.get(opp, "?"),
            "score_for": f,
            "score_against": a,
            "result": res,
            "competition": comp_names[m.competition_id][0],
        }

    recent = [item(m) for m in ms if m.status == MatchStatus.FINISHED][:10]
    nxt = [
        item(m)
        for m in reversed(
            [m for m in ms if m.status == MatchStatus.SCHEDULED and m.kickoff_at > now]
        )
    ][:3]
    last_comp = ms[0].competition_id if ms else None
    elo_info = None
    if last_comp:
        ratings = elo.ratings(load_finished(db, last_comp))
        if team_id in ratings:
            rank = 1 + sum(v > ratings[team_id] for v in ratings.values())
            elo_info = {
                "rating": ratings[team_id],
                "rank": rank,
                "of": len(ratings),
                "league": comp_names[last_comp][0],
            }
    leagues_ = sorted({comp_names[m.competition_id][0] for m in ms})
    return {
        "id": t.id,
        "name": t.name,
        "country": t.country,
        "leagues": leagues_,
        "recent": recent,
        "next": nxt,
        "elo": elo_info,
        "form": {
            k: team_form(db, team_id, now + __import__("datetime").timedelta(days=1), w, v)
            for k, (w, v) in {
                "last5": (5, "all"),
                "last10": (10, "all"),
                "home": (10, "home"),
                "away": (10, "away"),
            }.items()
        },
    }


def search_matches(
    db: Session,
    *,
    league_id: int | None = None,
    competition_id: int | None = None,
    team_q: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    H, A = aliased(Team), aliased(Team)
    q = (
        select(Match, H.name, A.name, Competition.name, Competition.season)
        .join(H, H.id == Match.home_team_id)
        .join(A, A.id == Match.away_team_id)
        .join(Competition, Competition.id == Match.competition_id)
    )
    if league_id:
        q = q.where(Match.competition_id.in_(sibling_ids(db, league_id)))
    if competition_id:
        q = q.where(Match.competition_id == competition_id)
    if status:
        q = q.where(Match.status == MatchStatus(status))
    if date_from:
        q = q.where(Match.kickoff_at >= date_from)
    if date_to:
        q = q.where(Match.kickoff_at < date_to)
    if team_q and team_q.strip():
        key = norm_key(team_q)
        ids = [t.id for t in db.scalars(select(Team)) if key in norm_key(t.name)]
        q = (
            q.where(Match.home_team_id.in_(ids) | Match.away_team_id.in_(ids))
            if ids
            else q.where(Match.id < 0)
        )
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    q = (
        q.order_by(Match.kickoff_at.desc() if order == "desc" else Match.kickoff_at.asc(), Match.id)
        .limit(limit)
        .offset(offset)
    )
    items = [
        {
            "id": m.id,
            "kickoff_at": m.kickoff_at.isoformat(),
            "status": m.status.value,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home": hn,
            "away": an,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "competition": cn,
            "season": cs,
            "source": m.source.value,
        }
        for m, hn, an, cn, cs in db.execute(q)
    ]
    return {"total": total, "items": items, "limit": limit, "offset": offset}


def global_search(db: Session, q: str) -> dict:
    key = norm_key(q)
    if len(key) < 2:
        return {"teams": [], "leagues": []}
    teams = [
        {"id": t.id, "name": t.name}
        for t in db.scalars(select(Team).order_by(Team.name))
        if key in norm_key(t.name)
    ][:8]
    lg = [{"id": x["id"], "name": x["name"]} for x in leagues(db) if key in norm_key(x["name"])][:5]
    return {"teams": teams, "leagues": lg}
