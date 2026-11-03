"""Import CSV de matchs (+ statistiques et cotes optionnelles), format natif ou football-data.co.uk.

Règles : validation stricte ligne par ligne, tout-ou-rien (une seule erreur => rien n'est écrit), aucune valeur
inventée (cellule vide = donnée absente), doublons ignorés. Un match déjà connu mais encore « programmé » reçoit son
résultat (et règle les prédictions enregistrées). Chaque import réel est tracé dans un lot, annulable.
"""

import csv
import difflib
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, ImportBatch, Match, MatchStatistics, Odds, Team, TeamAlias
from app.models.mixins import DataSource, utcnow
from app.models.sports import MatchStatus
from app.services.csv_adapters import to_native
from app.services.names import norm_key

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
CLOSING_BOOKMAKER = "Clôture (moyenne marché)"
PRE_BOOKMAKER = "Cotes avant-match (football-data)"
ODDS_COLS = ["close_home", "close_draw", "close_away", "pre_home", "pre_draw", "pre_away"]
OPTIONAL = (
    ["season", "home_score_ht", "away_score_ht"]
    + ODDS_COLS
    + [f"{s}_{k}" for s in ("home", "away") for k in STAT_FIELDS]
)
SIMILAR_CUTOFF = 0.86


def _odds3(v):
    if v is not None and any(x <= 1 for x in v):
        raise ValueError("cotes : toutes doivent être > 1")
    return v


class Row(BaseModel):
    date: datetime
    competition: str = Field(min_length=1, max_length=150)
    season: str | None = Field(default=None, max_length=20)
    home_team: str = Field(min_length=1, max_length=120)
    away_team: str = Field(min_length=1, max_length=120)
    home_score: int | None = Field(default=None, ge=0, le=99)
    away_score: int | None = Field(default=None, ge=0, le=99)
    home_score_ht: int | None = Field(default=None, ge=0, le=99)
    away_score_ht: int | None = Field(default=None, ge=0, le=99)
    stats: dict[str, dict[str, float | None]] = {}
    close: tuple[float, float, float] | None = None
    pre: tuple[float, float, float] | None = None

    _c = field_validator("close", "pre")(lambda cls, v: _odds3(v))

    @field_validator("date")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)

    @model_validator(mode="after")
    def _scores(self) -> "Row":
        if (self.home_score is None) != (self.away_score is None):
            raise ValueError("les deux scores ensemble ou aucun")
        if self.home_score is None and self.date < utcnow() - timedelta(days=1):
            raise ValueError(
                "score manquant pour un match déjà passé"
            )  # évite un résultat oublié silencieux
        return self


@dataclass
class ImportReport:
    rows: int = 0
    created_matches: int = 0
    updated_matches: int = 0
    skipped_duplicates: int = 0
    created_teams: int = 0
    created_competitions: int = 0
    enriched_odds: int = 0
    errors: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False
    source_format: str = "native"
    batch_id: int | None = None


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


def _triple(d: dict, prefix: str):
    vals = tuple(_num(d.get(f"{prefix}_{k}"), as_int=False) for k in ("home", "draw", "away"))
    if any(x is not None for x in vals) and not all(x is not None for x in vals):
        raise ValueError(f"cotes {prefix} : les trois colonnes ensemble ou aucune")
    return vals if vals[0] is not None else None


def parse(text: str, max_rows: int = MAX_ROWS) -> tuple[list[tuple[int, Row]], list[dict]]:
    first = text.lstrip("\ufeff").split("\n", 1)[0]
    reader = csv.DictReader(
        io.StringIO(text.lstrip("\ufeff")),
        delimiter=";" if first.count(";") > first.count(",") else ",",
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
            stats = {
                s: {
                    col: _num(d.get(f"{s}_{k}"), as_int=(k != "possession"))
                    for k, col in STAT_FIELDS.items()
                }
                for s in ("home", "away")
            }
            r = Row(
                date=d["date"],
                competition=d["competition"],
                season=d.get("season") or None,
                home_team=d["home_team"],
                away_team=d["away_team"],
                home_score=d["home_score"] or None,
                away_score=d["away_score"] or None,
                home_score_ht=d.get("home_score_ht") or None,
                away_score_ht=d.get("away_score_ht") or None,
                stats=stats,
                close=_triple(d, "close"),
                pre=_triple(d, "pre"),
            )
            if norm_key(r.home_team) == norm_key(r.away_team):
                raise ValueError("une équipe ne peut pas jouer contre elle-même")
            rows.append((i, r))
        except (ValidationError, ValueError) as e:
            msg = (
                "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
                if isinstance(e, ValidationError)
                else str(e)
            )
            errors.append({"line": i, "error": msg})
    return rows, errors


def _add_odds(db: Session, match_id: int, bookmaker: str, triple, when: datetime) -> None:
    for sel, price in zip(("home", "draw", "away"), triple, strict=True):
        db.add(
            Odds(
                match_id=match_id,
                bookmaker=bookmaker,
                market="1X2",
                selection=sel,
                price=price,
                recorded_at=when,
                source=DataSource.MANUAL,
            )
        )


def _latest_prices(db: Session, match_id: int, bookmaker: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for o in db.scalars(
        select(Odds)
        .where(Odds.match_id == match_id, Odds.bookmaker == bookmaker, Odds.market == "1X2")
        .order_by(Odds.recorded_at, Odds.id)
    ):
        out[o.selection] = o.price
    return out


def import_csv(
    db: Session,
    text: str,
    dry_run: bool = False,
    max_rows: int = MAX_ROWS,
    competition: str | None = None,
    season: str | None = None,
    since_year: int | None = None,
    user_id: int | None = None,
    source: str = "upload",
    label: str = "",
) -> ImportReport:
    text, fmt = to_native(text, competition, season, since_year)
    rows, errors = parse(text, max_rows)
    rep = ImportReport(
        rows=len(rows) + len(errors), errors=errors, dry_run=dry_run, source_format=fmt
    )
    if errors:
        return rep  # tout-ou-rien

    # Résolution insensible à la casse, aux accents et à la ponctuation ; alias prioritaires.
    teams: dict[str, Team] = {}
    for t in db.scalars(select(Team)):
        teams.setdefault(norm_key(t.name), t)
    for al in db.scalars(select(TeamAlias)):
        if (t := db.get(Team, al.team_id)) is not None:
            teams[al.alias_key] = t
    comps: dict[tuple[str, str | None], Competition] = {}
    for c in db.scalars(select(Competition)):
        comps.setdefault((norm_key(c.name), c.season), c)
    known_keys = list(teams)

    batch = ImportBatch(
        user_id=user_id, source=source, label=label[:255] or "import", rows=rep.rows
    )
    db.add(batch)
    db.flush()
    seen: dict[tuple, int] = {}
    to_settle: list[int] = []
    now = utcnow()

    def team(name: str) -> Team:
        key = norm_key(name)
        if key not in teams:
            t = Team(name=name.strip(), source=DataSource.MANUAL)
            db.add(t)
            db.flush()
            rep.created_teams += 1
            if len(rep.warnings) < 20 and (
                close := difflib.get_close_matches(key, known_keys, n=1, cutoff=SIMILAR_CUTOFF)
            ):
                rep.warnings.append(
                    f"Équipe créée « {t.name} » : ressemble à « {teams[close[0]].name} ». Si c'est la même, fusionnez-les (Centre de données > Équipes)."
                )
            teams[key] = t
        return teams[key]

    def comp(name: str, season: str | None) -> Competition:
        key = (norm_key(name), season)
        if key not in comps:
            c = Competition(name=name.strip(), season=season, source=DataSource.MANUAL)
            db.add(c)
            db.flush()
            rep.created_competitions += 1
            comps[key] = c
        return comps[key]

    for _, r in rows:
        c, h, a = comp(r.competition, r.season), team(r.home_team), team(r.away_team)
        key = (c.id, h.id, a.id, r.date.date())
        known = (
            db.get(Match, seen[key])
            if key in seen
            else db.scalar(
                select(Match)
                .where(
                    Match.competition_id == c.id,
                    Match.home_team_id == h.id,
                    Match.away_team_id == a.id,
                    Match.kickoff_at >= r.date - timedelta(days=1),
                    Match.kickoff_at <= r.date + timedelta(days=1),
                )
                .limit(1)
            )
        )
        if known is not None:
            if known.status == MatchStatus.SCHEDULED and r.home_score is not None:
                # le match programmé reçoit son résultat (et ses statistiques / cotes)
                known.status, known.home_score, known.away_score = (
                    MatchStatus.FINISHED,
                    r.home_score,
                    r.away_score,
                )
                known.home_score_ht, known.away_score_ht = r.home_score_ht, r.away_score_ht
                _stats_rows(db, known.id, h, a, r)
                if r.close and not _latest_prices(db, known.id, CLOSING_BOOKMAKER):
                    _add_odds(db, known.id, CLOSING_BOOKMAKER, r.close, r.date)
                rep.updated_matches += 1
                to_settle.append(known.id)
            else:
                rep.skipped_duplicates += 1
                if r.close and not _latest_prices(db, known.id, CLOSING_BOOKMAKER):
                    _add_odds(db, known.id, CLOSING_BOOKMAKER, r.close, r.date)  # enrichissement
                    rep.enriched_odds += 1
                if r.pre and known.status == MatchStatus.SCHEDULED:
                    cur = _latest_prices(db, known.id, PRE_BOOKMAKER)
                    if [cur.get(s) for s in ("home", "draw", "away")] != list(r.pre):
                        _add_odds(
                            db, known.id, PRE_BOOKMAKER, r.pre, now
                        )  # nouvelles cotes : l'historique est conservé
                        rep.enriched_odds += 1
            continue
        m = Match(
            competition_id=c.id,
            home_team_id=h.id,
            away_team_id=a.id,
            kickoff_at=r.date,
            status=MatchStatus.FINISHED if r.home_score is not None else MatchStatus.SCHEDULED,
            home_score=r.home_score,
            away_score=r.away_score,
            home_score_ht=r.home_score_ht,
            away_score_ht=r.away_score_ht,
            source=DataSource.MANUAL,
            import_batch_id=batch.id,
        )
        db.add(m)
        db.flush()
        seen[key] = m.id
        _stats_rows(db, m.id, h, a, r)
        if r.close:
            _add_odds(db, m.id, CLOSING_BOOKMAKER, r.close, r.date)
        if r.pre and m.status == MatchStatus.SCHEDULED:
            _add_odds(db, m.id, PRE_BOOKMAKER, r.pre, now)
        rep.created_matches += 1

    batch.created_matches, batch.updated_matches = rep.created_matches, rep.updated_matches
    batch.skipped, batch.created_teams = rep.skipped_duplicates, rep.created_teams
    rep.batch_id = batch.id
    if not (rep.created_matches or rep.updated_matches or rep.enriched_odds):
        db.delete(batch)  # rien changé : pas de lot à tracer
        rep.batch_id = None
    if dry_run:
        db.rollback()
        rep.batch_id = None
    else:
        db.commit()
        if to_settle:
            from app.services.tracking import settle_match  # import tardif : évite un cycle

            for mid in to_settle:
                if (m := db.get(Match, mid)) is not None:
                    settle_match(db, m)
    return rep


def _stats_rows(db: Session, match_id: int, h: Team, a: Team, r: Row) -> None:
    for side, t in (("home", h), ("away", a)):
        vals = r.stats.get(side, {})
        if any(v is not None for v in vals.values()):
            if (
                db.scalar(
                    select(MatchStatistics.id).where(
                        MatchStatistics.match_id == match_id, MatchStatistics.team_id == t.id
                    )
                )
                is None
            ):
                db.add(
                    MatchStatistics(
                        match_id=match_id, team_id=t.id, source=DataSource.MANUAL, **vals
                    )
                )
