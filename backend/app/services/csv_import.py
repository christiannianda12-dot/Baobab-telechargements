"""Import CSV de matchs terminés (+ statistiques optionnelles).

Règles : validation stricte ligne par ligne, tout-ou-rien (une seule erreur => rien n'est écrit),
aucune valeur par défaut inventée (cellule vide = donnée absente), doublons ignorés.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, Match, MatchStatistics, Team
from app.models.mixins import DataSource
from app.models.sports import MatchStatus
from app.services.csv_adapters import to_native

MAX_ROWS = 5000
REQUIRED = ["date", "competition", "home_team", "away_team", "home_score", "away_score"]
STAT_FIELDS = {  # suffixe CSV -> colonne MatchStatistics
    "shots": "shots",
    "shots_on_target": "shots_on_target",
    "corners": "corners",
    "possession": "possession_pct",
    "fouls": "fouls",
    "yellow": "yellow_cards",
    "red": "red_cards",
}
OPTIONAL = ["season", "home_score_ht", "away_score_ht"] + [
    f"{side}_{k}" for side in ("home", "away") for k in STAT_FIELDS
]


class Row(BaseModel):
    date: datetime
    competition: str = Field(min_length=1, max_length=150)
    season: str | None = Field(default=None, max_length=20)
    home_team: str = Field(min_length=1, max_length=120)
    away_team: str = Field(min_length=1, max_length=120)
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)
    home_score_ht: int | None = Field(default=None, ge=0, le=99)
    away_score_ht: int | None = Field(default=None, ge=0, le=99)
    stats: dict[str, dict[str, float | None]] = {}

    @field_validator("date")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)


@dataclass
class ImportReport:
    rows: int = 0
    created_matches: int = 0
    skipped_duplicates: int = 0
    created_teams: int = 0
    created_competitions: int = 0
    errors: list[dict] = field(default_factory=list)
    dry_run: bool = False
    source_format: str = "native"


def _num(raw: str | None, as_int: bool):
    raw = (raw or "").strip().replace(",", ".")
    if raw == "":
        return None
    v = float(raw)
    if as_int:
        if v != int(v) or v < 0:
            raise ValueError(f"entier positif attendu, reçu {raw!r}")
        return int(v)
    return v


def parse(text: str, max_rows: int = MAX_ROWS) -> tuple[list[tuple[int, Row]], list[dict]]:
    reader = csv.DictReader(
        io.StringIO(text.lstrip("﻿")),
        delimiter=";"
        if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",")
        else ",",
    )
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in header]
    unknown = [c for c in header if c and c not in REQUIRED + OPTIONAL]
    if missing or unknown:
        msg = []
        if missing:
            msg.append(f"colonnes manquantes : {missing}")
        if unknown:
            msg.append(f"colonnes inconnues : {unknown}")
        return [], [{"line": 1, "error": " ; ".join(msg)}]
    reader.fieldnames = header
    rows, errors = [], []
    for i, raw in enumerate(reader, start=2):
        if len(rows) + len(errors) >= max_rows:
            errors.append({"line": i, "error": f"Maximum {max_rows} lignes par import."})
            break
        try:
            d = {k: (v or "").strip() for k, v in raw.items() if k}
            stats: dict[str, dict[str, float | None]] = {"home": {}, "away": {}}
            for side in ("home", "away"):
                for k, col in STAT_FIELDS.items():
                    stats[side][col] = _num(d.get(f"{side}_{k}"), as_int=(k != "possession"))
            rows.append(
                (
                    i,
                    Row(
                        date=d["date"],
                        competition=d["competition"],
                        season=d.get("season") or None,
                        home_team=d["home_team"],
                        away_team=d["away_team"],
                        home_score=d["home_score"],
                        away_score=d["away_score"],
                        home_score_ht=d.get("home_score_ht") or None,
                        away_score_ht=d.get("away_score_ht") or None,
                        stats=stats,
                    ),
                )
            )
            if rows[-1][1].home_team.lower() == rows[-1][1].away_team.lower():
                raise ValueError("une équipe ne peut pas jouer contre elle-même")
        except (ValidationError, ValueError) as e:
            rows = [r for r in rows if r[0] != i]
            msg = (
                "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
                if isinstance(e, ValidationError)
                else str(e)
            )
            errors.append({"line": i, "error": msg})
    return rows, errors


def import_csv(
    db: Session,
    text: str,
    dry_run: bool = False,
    max_rows: int = MAX_ROWS,
    competition: str | None = None,
    season: str | None = None,
) -> ImportReport:
    text, fmt = to_native(text, competition, season)
    rows, errors = parse(text, max_rows)
    rep = ImportReport(
        rows=len(rows) + len(errors), errors=errors, dry_run=dry_run, source_format=fmt
    )
    if errors:
        return rep  # tout-ou-rien

    # Comparaison insensible à la casse faite en Python (SQLite ne met en minuscules que l'ASCII :
    # « Atlético » ne serait jamais retrouvé via lower() et serait recréé à chaque import).
    teams: dict[str, Team] = {}
    for t in db.scalars(select(Team)):
        teams.setdefault(t.name.strip().casefold(), t)
    comps: dict[tuple[str, str | None], Competition] = {}
    for c in db.scalars(select(Competition)):
        comps.setdefault((c.name.strip().casefold(), c.season), c)
    seen: set[tuple] = set()

    def team(name: str) -> Team:
        key = name.strip().casefold()
        if key not in teams:
            t = Team(name=name.strip(), source=DataSource.MANUAL)
            db.add(t)
            db.flush()
            rep.created_teams += 1
            teams[key] = t
        return teams[key]

    def comp(name: str, season: str | None) -> Competition:
        key = (name.strip().casefold(), season)
        if key not in comps:
            c = Competition(name=name.strip(), season=season, source=DataSource.MANUAL)
            db.add(c)
            db.flush()
            rep.created_competitions += 1
            comps[key] = c
        return comps[key]

    for _, r in rows:
        c, h, a = comp(r.competition, r.season), team(r.home_team), team(r.away_team)
        key = (c.id, h.id, a.id, r.date)
        exists = key in seen or db.scalar(
            select(Match.id).where(
                Match.competition_id == c.id,
                Match.home_team_id == h.id,
                Match.away_team_id == a.id,
                Match.kickoff_at == r.date,
            )
        )
        if exists:
            rep.skipped_duplicates += 1
            continue
        seen.add(key)
        m = Match(
            competition_id=c.id,
            home_team_id=h.id,
            away_team_id=a.id,
            kickoff_at=r.date,
            status=MatchStatus.FINISHED,
            home_score=r.home_score,
            away_score=r.away_score,
            home_score_ht=r.home_score_ht,
            away_score_ht=r.away_score_ht,
            source=DataSource.MANUAL,
        )
        db.add(m)
        db.flush()
        for side, t in (("home", h), ("away", a)):
            vals = r.stats[side]
            if any(v is not None for v in vals.values()):
                db.add(
                    MatchStatistics(match_id=m.id, team_id=t.id, source=DataSource.MANUAL, **vals)
                )
        rep.created_matches += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return rep
